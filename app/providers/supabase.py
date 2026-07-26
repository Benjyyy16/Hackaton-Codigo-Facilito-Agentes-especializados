"""Provider de almacenamiento sobre Supabase.

Implementa ``StorageProvider``, no ``EventSourceProvider``. No expone ``sync`` ni
``fetch_events`` porque no es una fuente de eventos: es el almacén donde se guardan. Fingir esos
dos métodos obligaría a devolver vacío o a lanzar "no soportado", que es la interfaz gorda que
la segregación evita.

Lo que sí comparte con los demás providers es el ciclo de vida: conectar, informar de su salud y
cerrar. Eso es lo que hay en el puerto base.
"""

from __future__ import annotations

import time
from typing import ClassVar

from supabase import AsyncClient

from app.core.config import Settings
from app.core.exceptions import SupabaseError
from app.core.logging import get_logger
from app.integrations.supabase.client import (
    close_supabase_client,
    create_supabase_client,
    ping,
)
from app.providers.base import RepositoryBundle
from app.repositories.alerts import AlertRepository
from app.repositories.commitments import CommitmentRepository
from app.repositories.events import EventRepository
from app.repositories.risk_analyses import RiskAnalysisRepository
from app.repositories.workspaces import WorkspaceRepository
from app.schemas.common import DependencyStatus
from app.schemas.providers import ProviderHealth, ProviderKind

logger = get_logger("provider.supabase")

#: Nombre del provider de almacenamiento. No está en ``ProviderName`` a propósito: ese enum
#: enumera fuentes de eventos, que es lo que puede aparecer en la columna ``provider`` de un
#: evento y en la URL de un webhook. El almacén no aparece en ninguno de los dos.
STORAGE_PROVIDER_NAME = "supabase"


class SupabaseStorageProvider:
    """Supabase como almacén del dominio."""

    name: ClassVar[str] = STORAGE_PROVIDER_NAME
    kind: ClassVar[ProviderKind] = ProviderKind.STORAGE

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: AsyncClient | None = None

    async def connect(self) -> None:
        """Crea el cliente asíncrono. Es idempotente."""
        if self._client is not None:
            return
        self._client = await create_supabase_client(self._settings)

    async def close(self) -> None:
        await close_supabase_client(self._client)
        self._client = None

    async def health(self) -> ProviderHealth:
        """Comprueba que PostgREST responde. No eleva: informa (RF-2.3)."""
        if self._client is None:
            return ProviderHealth(
                provider=STORAGE_PROVIDER_NAME,
                status=DependencyStatus.UNKNOWN,
                detail="El almacenamiento no está conectado.",
            )

        started = time.perf_counter()
        reachable = await ping(self._client)
        return ProviderHealth(
            provider=STORAGE_PROVIDER_NAME,
            status=DependencyStatus.UP if reachable else DependencyStatus.DOWN,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    @property
    def is_connected(self) -> bool:
        """Indica si hay cliente.

        Lo consulta el health check, que debe poder preguntarlo sin provocar la excepción que
        eleva ``client``.
        """
        return self._client is not None

    @property
    def client(self) -> AsyncClient:
        """Cliente subyacente.

        Lo usa la construcción de repositorios y nada más. Ningún servicio debe llegar hasta
        aquí: el acceso a datos pasa por los repositorios (RF-7.2).
        """
        if self._client is None:
            raise SupabaseError("El cliente de Supabase no está inicializado.")
        return self._client

    def repositories(self) -> RepositoryBundle:
        """Construye los repositorios respaldados por este almacén."""
        client = self.client
        return RepositoryBundle(
            workspaces=WorkspaceRepository(client),
            events=EventRepository(client),
            commitments=CommitmentRepository(client),
            analyses=RiskAnalysisRepository(client),
            alerts=AlertRepository(client),
        )
