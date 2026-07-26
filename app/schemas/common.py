"""Schemas transversales a la API."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

ItemT = TypeVar("ItemT")

#: Límites de paginación. El máximo coincide con ``MAX_PAGE_SIZE`` del repositorio, de modo
#: que un cliente que pide más recibe 422 en lugar de un recorte silencioso (RF-10.6).
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

PageLimit = Annotated[
    int,
    Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Número de elementos por página.",
    ),
]
PageOffset = Annotated[
    int, Field(default=0, ge=0, description="Elementos a omitir desde el inicio.")
]


class PaginatedResponse(BaseModel, Generic[ItemT]):
    """Página de resultados con el total de coincidencias."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ItemT] = Field(description="Elementos de la página actual.")
    total: int = Field(description="Total de elementos que cumplen el filtro.")
    limit: int = Field(description="Tamaño de página aplicado.")
    offset: int = Field(description="Desplazamiento aplicado.")
    has_more: bool = Field(description="Indica si quedan más elementos por recuperar.")


class ServiceStatus(StrEnum):
    """Estado agregado del servicio."""

    OK = "ok"
    #: El servicio responde pero alguna dependencia no está disponible. Se devuelve con 200
    #: a propósito: un health check que falla al caerse una dependencia impide distinguir
    #: "el proceso está muerto" de "el proceso vive y su dependencia no" (RF-2.3).
    DEGRADED = "degraded"


class DependencyStatus(StrEnum):
    """Estado de una dependencia externa."""

    UP = "up"
    DOWN = "down"
    #: No se comprobó, por ejemplo porque el cliente aún no está inicializado.
    UNKNOWN = "unknown"


class DependencyHealth(BaseModel):
    """Salud de una dependencia concreta."""

    name: str = Field(description="Nombre de la dependencia.")
    status: DependencyStatus = Field(description="Estado observado.")
    latency_ms: float | None = Field(
        default=None, description="Tiempo de respuesta de la comprobación."
    )


class HealthResponse(BaseModel):
    """Respuesta de ``GET /health``.

    No incluye configuración ni credenciales: solo identidad del servicio y estado de sus
    dependencias (RF-2.2).
    """

    status: ServiceStatus = Field(description="Estado agregado del servicio.")
    service: str = Field(description="Nombre del servicio.")
    version: str = Field(description="Versión del servicio.")
    environment: str = Field(description="Entorno de ejecución.")
    dependencies: list[DependencyHealth] = Field(
        default_factory=list, description="Estado de cada dependencia comprobada."
    )
