"""Contratos de los providers.

Tipos que cruzan la frontera del puerto. Ningún provider concreto aparece aquí: son los datos
con los que la lógica de negocio habla con cualquier integración.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StrEnum

from app.schemas.common import DependencyStatus
from app.schemas.events import ProviderName


class ProviderKind(StrEnum):
    """Papel del provider en la arquitectura."""

    EVENT_SOURCE = "event_source"
    STORAGE = "storage"
    NOTIFICATION = "notification"


class ProviderCapability(StrEnum):
    """Lo que un provider sabe hacer."""

    SYNC = "sync"
    WEBHOOK = "webhook"
    NOTIFY = "notify"
    LOGS = "logs"
    EVENTS = "events"


class ProviderHealth(BaseModel):
    """Estado de un provider.

    ``provider`` es una cadena y no ``ProviderName`` porque también se informa de la salud del
    almacén, que no es una fuente de eventos y por tanto no pertenece a ese enum. La salud es un
    informe, no un identificador de enrutado.
    """

    model_config = ConfigDict(frozen=True)

    provider: str = Field(description="Provider comprobado.")
    status: DependencyStatus = Field(description="Estado observado.")
    latency_ms: float | None = Field(
        default=None, description="Tiempo de respuesta de la comprobación."
    )
    detail: str | None = Field(
        default=None, description="Motivo, cuando el estado no es correcto."
    )


class SyncRequest(BaseModel):
    """Petición de sincronización, en términos comunes a cualquier provider.

    ``workspace_key`` es el contenedor en el origen: clave de proyecto en Jira, repositorio en
    GitHub, base de datos en Notion. ``query`` es la consulta nativa del provider, opcional;
    cada uno la interpreta en su propio lenguaje, y si falta la construye él.
    """

    model_config = ConfigDict(frozen=True)

    workspace_key: str = Field(min_length=1, max_length=200)
    query: str | None = Field(default=None, max_length=2000)
    max_items: int | None = Field(default=None, ge=1, le=5000)


class SyncReport(BaseModel):
    """Resultado de una sincronización."""

    provider: ProviderName = Field(description="Provider sincronizado.")
    workspace_key: str = Field(description="Contenedor sincronizado.")
    query: str | None = Field(default=None, description="Consulta efectivamente ejecutada.")
    processed: int = Field(default=0)
    created: int = Field(default=0)
    skipped: int = Field(default=0)
    failed: int = Field(default=0)
    truncated: bool = Field(default=False)
    message: str | None = Field(default=None)


class ProviderInfo(BaseModel):
    """Descripción de un provider registrado, para ``GET /providers``."""

    provider: ProviderName = Field(description="Nombre del provider.")
    kind: ProviderKind = Field(description="Papel en la arquitectura.")
    capabilities: list[ProviderCapability] = Field(
        default_factory=list, description="Lo que sabe hacer."
    )
    health: ProviderHealth | None = Field(
        default=None, description="Estado, si se comprobó."
    )
