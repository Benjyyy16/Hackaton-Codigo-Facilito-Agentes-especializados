"""Acceso a datos de eventos externos.

Sirve a cualquier provider: la tabla guarda eventos de Jira, GitHub, Notion o cualquier otra
fuente, distinguidos por la columna ``provider``.
"""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.repositories.base import BaseRepository, Page, Row
from app.schemas.events import ProviderName


class EventRepository(BaseRepository):
    """Eventos recibidos de sistemas externos, con su payload original.

    No admite borrado lógico: el registro de eventos es un histórico y borrarlo falsearía el
    análisis.
    """

    table_name: ClassVar[str] = "external_events"
    soft_delete: ClassVar[bool] = False
    default_order_column: ClassVar[str] = "occurred_at"

    async def get_by_fingerprint(self, fingerprint: str) -> Row | None:
        """Devuelve el evento con esa huella, o ``None``.

        Es la comprobación previa de la deduplicación. La garantía real la da la restricción de
        unicidad en la tabla, porque entre esta lectura y la inserción cabe una condición de
        carrera (RF-6.2, RF-6.3). El provider ya forma parte del material de la huella, así que
        no hace falta filtrar por él aquí.
        """
        return await self.find_one({"fingerprint": fingerprint})

    async def list_events(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        workspace_id: UUID | None = None,
        provider: ProviderName | None = None,
        kind: str | None = None,
    ) -> Page[Row]:
        """Lista eventos del más reciente al más antiguo (RF-10.1, RF-10.2)."""
        return await self.list_page(
            limit=limit,
            offset=offset,
            filters={
                "workspace_id": str(workspace_id) if workspace_id else None,
                "provider": provider.value if provider else None,
                "kind": kind,
            },
            order_column="occurred_at",
            descending=True,
        )

    async def list_by_external_key(
        self, provider: ProviderName, external_key: str, *, limit: int = 20
    ) -> Page[Row]:
        """Historial de un elemento concreto, que es lo que alimenta el análisis técnico."""
        return await self.list_page(
            limit=limit,
            filters={"provider": provider.value, "external_key": external_key},
            order_column="occurred_at",
            descending=True,
        )

    async def get_latest_for_workspace(self, workspace_id: UUID) -> Row | None:
        """Último evento de un contenedor, para reanalizar por proyecto (RF-11.1)."""
        page = await self.list_page(
            limit=1,
            filters={"workspace_id": str(workspace_id)},
            order_column="occurred_at",
            descending=True,
        )
        return page.items[0] if page.items else None
