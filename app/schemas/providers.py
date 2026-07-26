"""Contratos de los providers.

Tipos que cruzan la frontera del puerto. Ningún provider concreto aparece aquí: son los datos
con los que la lógica de negocio habla con cualquier integración.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import DependencyStatus
from app.schemas.events import ProviderName


class ProviderKind(StrEnum):
    """Papel del provider en la arquitectura."""

    #: Aporta eventos: Jira, GitHub, Notion, AWS, Rightway.
    EVENT_SOURCE = "event_source"
    #: Persiste: Supabase.
    STORAGE = "storage"


class ProviderCapability(StrEnum):
    """Lo que un provider sabe hacer.

    Se declara en lugar de descubrirse al fallar. Un provider puede saber sincronizar pero no
    recibir webhooks, y la lógica que lo use debe poder preguntarlo antes de intentarlo.
    """

    #: Sabe recorrer el estado actual mediante una consulta.
    SYNC = "sync"
    #: Sabe recibir y validar webhooks.
    WEBHOOK = "webhook"


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
    """Resultado de una sincronización (RF-4.5)."""

    provider: ProviderName = Field(description="Provider sincronizado.")
    workspace_key: str = Field(description="Contenedor sincronizado.")
    query: str = Field(description="Consulta efectivamente ejecutada.")
    processed: int = Field(default=0, description="Elementos recuperados del origen.")
    created: int = Field(default=0, description="Eventos nuevos persistidos.")
    skipped: int = Field(default=0, description="Eventos omitidos por duplicados.")
    failed: int = Field(default=0, description="Elementos que no se pudieron procesar.")
    truncated: bool = Field(
        default=False, description="La recogida se detuvo por un límite."
    )


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
