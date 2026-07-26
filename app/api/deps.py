"""Dependencias de FastAPI.

Todo lo que las rutas necesitan se resuelve aquí, leyendo del estado de la aplicación. Ese
detalle es lo que permite que los tests sustituyan el cliente de Supabase o un servicio
completo con ``dependency_overrides``, sin parchear variables de módulo.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request

from app.core.config import Settings
from app.core.exceptions import IntegrationError, SupabaseError
from app.integrations.jira.client import JiraClient
from app.repositories.alerts import AlertRepository
from app.repositories.commitments import CommitmentRepository
from app.repositories.jira_events import JiraEventRepository
from app.repositories.projects import ProjectRepository
from app.repositories.risk_analyses import RiskAnalysisRepository
from app.services.health_service import HealthService

# --- Estado de la aplicación --------------------------------------------------------


def get_settings_dep(request: Request) -> Settings:
    """Configuración resuelta en el arranque."""
    return request.app.state.settings


def get_supabase_client(request: Request) -> Any:
    """Cliente de Supabase creado en el ``lifespan``.

    Si no está disponible es que el arranque no lo inicializó; se traduce a un error de
    dominio en lugar de dejar que falle como ``AttributeError``.
    """
    client = getattr(request.app.state, "supabase", None)
    if client is None:
        raise SupabaseError("El cliente de Supabase no está inicializado.")
    return client


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SupabaseDep = Annotated[Any, Depends(get_supabase_client)]


def get_jira_client(request: Request, settings: SettingsDep) -> JiraClient:
    """Cliente de Jira sobre el ``httpx.AsyncClient`` creado en el ``lifespan``."""
    http = getattr(request.app.state, "jira_http", None)
    if http is None:
        raise IntegrationError("El cliente de Jira no está inicializado.")
    return JiraClient(http, max_retries=settings.HTTP_MAX_RETRIES)


JiraClientDep = Annotated[JiraClient, Depends(get_jira_client)]


# --- Repositorios -------------------------------------------------------------------


def get_project_repository(client: SupabaseDep) -> ProjectRepository:
    return ProjectRepository(client)


def get_jira_event_repository(client: SupabaseDep) -> JiraEventRepository:
    return JiraEventRepository(client)


def get_commitment_repository(client: SupabaseDep) -> CommitmentRepository:
    return CommitmentRepository(client)


def get_risk_analysis_repository(client: SupabaseDep) -> RiskAnalysisRepository:
    return RiskAnalysisRepository(client)


def get_alert_repository(client: SupabaseDep) -> AlertRepository:
    return AlertRepository(client)


ProjectRepositoryDep = Annotated[ProjectRepository, Depends(get_project_repository)]
JiraEventRepositoryDep = Annotated[
    JiraEventRepository, Depends(get_jira_event_repository)
]
CommitmentRepositoryDep = Annotated[
    CommitmentRepository, Depends(get_commitment_repository)
]
RiskAnalysisRepositoryDep = Annotated[
    RiskAnalysisRepository, Depends(get_risk_analysis_repository)
]
AlertRepositoryDep = Annotated[AlertRepository, Depends(get_alert_repository)]


# --- Servicios ----------------------------------------------------------------------


def get_health_service(request: Request, settings: SettingsDep) -> HealthService:
    """Servicio de salud.

    Toma el cliente con ``getattr`` en lugar de con la dependencia: el health check debe
    poder responder incluso si el cliente no llegó a inicializarse, informando de que la
    dependencia no se pudo comprobar.
    """
    return HealthService(settings, getattr(request.app.state, "supabase", None))


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]


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

    Punto de extensión para la autenticación JWT: cuando se implemente, esta función validará
    el token y las rutas no cambiarán.
    """
    return SERVICE_PRINCIPAL


PrincipalDep = Annotated[Principal, Depends(get_current_principal)]
