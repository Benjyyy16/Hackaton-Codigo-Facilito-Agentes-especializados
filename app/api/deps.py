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

from fastapi import Depends, Request

from app.agents.orchestrator import OrchestratorAgent
from app.core.config import Settings
from app.core.exceptions import SupabaseError
from app.core.logging import get_logger
from app.providers.base import RepositoryBundle
from app.providers.registry import ProviderRegistry
from app.providers.supabase import SupabaseStorageProvider
from app.services.health_service import HealthService
from app.services.ingest_service import IngestOutcome, IngestService
from app.services.orchestrator_service import OrchestratorService

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
