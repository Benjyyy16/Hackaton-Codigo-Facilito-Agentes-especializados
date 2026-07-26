"""Dependencias de FastAPI.

Todo lo que las rutas necesitan se resuelve aquí, leyendo del estado de la aplicación. Ese
detalle es lo que permite que los tests sustituyan un provider o un servicio completo con
``dependency_overrides``, sin parchear variables de módulo.

Ninguna dependencia menciona una clase concreta de provider: entregan el registro o el puerto.
Las implementaciones se eligen en la factoría del ``lifespan``, que es donde debe estar esa
decisión.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dataclasses import dataclass

from app.agents.orchestrator import OrchestratorAgent
from app.core.config import Settings
from app.core.exceptions import SupabaseError
from app.core.logging import get_logger
from app.providers.base import RepositoryBundle
from app.providers.registry import ProviderRegistry
from app.providers.supabase import SupabaseStorageProvider
from app.repositories.domain import (
    AgentRunRepository,
    AlertRepository as DomainAlertRepository,
    CommitmentRepository as DomainCommitmentRepository,
    DecisionRepository,
    DocumentRepository,
    EvidenceRepository,
    FindingRepository,
    ProjectRepository,
    RiskCaseRepository,
    SourceEventRepository,
    TimelineRepository,
)
from app.schemas.auth import CurrentUser
from app.services.analysis_service import AnalysisService
from app.services.auth_service import AuthService, AuthenticationError
from app.services.decision_service import DecisionService
from app.services.health_service import HealthService
from app.services.ingest_service import IngestOutcome, IngestService
from app.services.orchestrator_service import OrchestratorService
from app.websocket.manager import ConnectionManager

logger = get_logger("api.deps")


# --- Estado de la aplicación --------------------------------------------------------


def get_settings_dep(request: Request) -> Settings:
    """Configuración resuelta en el arranque."""
    return request.app.state.settings


def get_provider_registry(request: Request) -> ProviderRegistry:
    """Registro de providers construido en el ``lifespan``."""
    registry = getattr(request.app.state, "providers", None)
    if registry is None:
        # No debería ocurrir: el registro se crea siempre, aunque quede vacío.
        return ProviderRegistry()
    return registry


def get_storage(request: Request) -> SupabaseStorageProvider:
    """Provider de almacenamiento.

    Es la única dependencia que nombra una implementación concreta, y solo porque hay un único
    almacén. Lo que entrega hacia arriba es el conjunto de repositorios, no el cliente.
    """
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise SupabaseError("El almacenamiento no está inicializado.")
    return storage


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ProviderRegistryDep = Annotated[ProviderRegistry, Depends(get_provider_registry)]
StorageDep = Annotated[SupabaseStorageProvider, Depends(get_storage)]


# --- Repositorios -------------------------------------------------------------------


def get_repositories(storage: StorageDep) -> RepositoryBundle:
    """Repositorios respaldados por el almacén configurado.

    Los servicios reciben este conjunto y nunca el cliente: el acceso a datos pasa siempre por un
    repositorio (RF-7.2).
    """
    return storage.repositories()


RepositoriesDep = Annotated[RepositoryBundle, Depends(get_repositories)]


# --- Servicios ----------------------------------------------------------------------


def get_ingest_service(repositories: RepositoriesDep) -> IngestService:
    return IngestService(repositories.workspaces, repositories.events)


IngestServiceDep = Annotated[IngestService, Depends(get_ingest_service)]


def get_orchestrator_service(
    registry: ProviderRegistryDep,
    repositories: RepositoriesDep,
    ingest: IngestServiceDep,
    settings: SettingsDep,
) -> OrchestratorService:
    return OrchestratorService(
        registry,
        repositories,
        ingest,
        OrchestratorAgent(),
        alert_threshold=settings.RISK_ALERT_THRESHOLD,
    )


OrchestratorServiceDep = Annotated[
    OrchestratorService, Depends(get_orchestrator_service)
]


def get_health_service(request: Request, settings: SettingsDep) -> HealthService:
    """Servicio de salud.

    Toma el almacén y el registro con ``getattr`` en lugar de con las dependencias: el health
    check debe poder responder incluso si el arranque no llegó a inicializarlos, informando de
    que no se pudieron comprobar.
    """
    storage = getattr(request.app.state, "storage", None)
    return HealthService(
        settings,
        storage.client if storage is not None and storage.is_connected else None,
        registry=getattr(request.app.state, "providers", None),
    )


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]


# --- Trabajo posterior a la ingesta -------------------------------------------------

PostIngestHook = Callable[[IngestOutcome], Awaitable[None]]


def get_post_ingest_hook(
    orchestrator: OrchestratorServiceDep,
) -> PostIngestHook:
    """Devuelve el trabajo que se ejecuta tras persistir un evento.

    Envuelve el análisis en un manejador de errores propio. Se ejecuta como tarea en segundo
    plano, ya con el evento persistido y la respuesta enviada, así que un fallo aquí debe quedar
    registrado sin tumbar nada ni perder el evento (RF-5.8).
    """

    async def _run(outcome: IngestOutcome) -> None:
        try:
            await orchestrator.analyse_outcome(outcome)
        except Exception as error:  # noqa: BLE001 - una tarea de fondo no debe propagar
            logger.error(
                "El análisis posterior a la ingesta falló para %s",
                outcome.event.external_key,
                exc_info=error,
            )

    return _run


PostIngestHookDep = Annotated[PostIngestHook, Depends(get_post_ingest_hook)]


# --- Autorización -------------------------------------------------------------------


class Principal:
    """Identidad que ejecuta la petición.

    Hoy siempre es el propio servicio. Existe para que activar JWT más adelante no obligue a
    cambiar la firma de las rutas (RNF-1.6).
    """

    __slots__ = ("kind", "subject")

    def __init__(self, subject: str, kind: str = "service") -> None:
        self.subject = subject
        self.kind = kind

    @property
    def is_service(self) -> bool:
        return self.kind == "service"

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"Principal(subject={self.subject!r}, kind={self.kind!r})"


SERVICE_PRINCIPAL = Principal(subject="commitment-twin-backend")


async def get_current_principal() -> Principal:
    """Devuelve la identidad actual.

    Punto de extensión para la autenticación JWT: cuando se implemente, esta función validará el
    token y las rutas no cambiarán.
    """
    return SERVICE_PRINCIPAL


PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


# --- Autenticación JWT ---------------------------------------------------------------


def get_auth_service(settings: SettingsDep) -> AuthService:
    """Crea el servicio de autenticación."""
    return AuthService(settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


security = HTTPBearer()


async def get_current_user_optional(
    request: Request, auth_service: AuthServiceDep
) -> CurrentUser | None:
    """Extrae el usuario del JWT si está presente, sino devuelve None."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]  # "Bearer " = 7 caracteres
    try:
        return auth_service.get_current_user(token)
    except AuthenticationError:
        return None


OptionalUserDep = Annotated[CurrentUser | None, Depends(get_current_user_optional)]


async def get_current_user_required(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    auth_service: AuthServiceDep,
) -> CurrentUser:
    """Extrae el usuario del JWT. Requiere que el token esté presente y sea válido."""
    try:
        return auth_service.get_current_user(credentials.credentials)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user_required)]


# --- Repositorios del dominio Datgent ------------------------------------------------


@dataclass(frozen=True)
class DomainRepositoryBundle:
    """Repositorios del dominio Datgent, creados desde el cliente de Supabase."""

    projects: ProjectRepository
    commitments: DomainCommitmentRepository
    source_events: SourceEventRepository
    agent_runs: AgentRunRepository
    findings: FindingRepository
    evidence: EvidenceRepository
    risk_cases: RiskCaseRepository
    alerts: DomainAlertRepository
    decisions: DecisionRepository
    timeline: TimelineRepository
    documents: DocumentRepository


def get_domain_repositories(storage: StorageDep) -> DomainRepositoryBundle:
    """Construye los repositorios del dominio a partir del cliente del almacén."""
    client = storage.client
    return DomainRepositoryBundle(
        projects=ProjectRepository(client),
        commitments=DomainCommitmentRepository(client),
        source_events=SourceEventRepository(client),
        agent_runs=AgentRunRepository(client),
        findings=FindingRepository(client),
        evidence=EvidenceRepository(client),
        risk_cases=RiskCaseRepository(client),
        alerts=DomainAlertRepository(client),
        decisions=DecisionRepository(client),
        timeline=TimelineRepository(client),
        documents=DocumentRepository(client),
    )


DomainRepositoriesDep = Annotated[DomainRepositoryBundle, Depends(get_domain_repositories)]


# --- Servicios del dominio Datgent ---------------------------------------------------


def get_ws_manager(request: Request) -> ConnectionManager:
    """Gestor de WebSocket, creado en create_app."""
    manager = getattr(request.app.state, "ws_manager", None)
    if manager is None:
        manager = ConnectionManager()
    return manager


WsManagerDep = Annotated[ConnectionManager, Depends(get_ws_manager)]


def get_analysis_service(
    repos: DomainRepositoriesDep,
    ws_manager: WsManagerDep,
    settings: SettingsDep,
) -> AnalysisService:
    """Crea el servicio de análisis con todos sus repositorios."""
    return AnalysisService(
        projects=repos.projects,
        commitments=repos.commitments,
        source_events=repos.source_events,
        agent_runs=repos.agent_runs,
        findings=repos.findings,
        evidence=repos.evidence,
        risk_cases=repos.risk_cases,
        alerts=repos.alerts,
        decisions=repos.decisions,
        timeline=repos.timeline,
        documents=repos.documents,
        ws_manager=ws_manager,
        risk_alert_threshold=settings.RISK_ALERT_THRESHOLD,
    )


AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]


def get_decision_service(
    repos: DomainRepositoriesDep,
    ws_manager: WsManagerDep,
) -> DecisionService:
    """Crea el servicio de decisiones."""
    return DecisionService(
        decisions=repos.decisions,
        timeline=repos.timeline,
        ws_manager=ws_manager,
    )


DecisionServiceDep = Annotated[DecisionService, Depends(get_decision_service)]
