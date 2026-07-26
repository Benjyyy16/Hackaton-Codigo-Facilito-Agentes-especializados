"""Acceso a datos de eventos de Jira."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from app.repositories.base import BaseRepository, Page, Row


class JiraEventRepository(BaseRepository):
    """Eventos recibidos de Jira, con su payload original.

    No admite borrado lógico: el registro de eventos es un histórico y borrarlo falsearía el
    análisis.
    """

    table_name: ClassVar[str] = "jira_events"
    soft_delete: ClassVar[bool] = False
    default_order_column: ClassVar[str] = "occurred_at"

    async def get_by_fingerprint(self, fingerprint: str) -> Row | None:
        """Devuelve el evento con esa huella, o ``None``.

        Es la comprobación previa de la deduplicación. La garantía real la da la restricción
        de unicidad en la tabla, porque entre esta lectura y la inserción cabe una condición
        de carrera (RF-6.2, RF-6.3).
        """
        return await self.find_one({"fingerprint": fingerprint})

    async def list_events(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        project_id: UUID | None = None,
        event_type: str | None = None,
    ) -> Page[Row]:
        """Lista eventos del más reciente al más antiguo (RF-10.1, RF-10.2)."""
        return await self.list_page(
            limit=limit,
            offset=offset,
            filters={
                "project_id": str(project_id) if project_id else None,
                "event_type": event_type,
            },
            order_column="occurred_at",
            descending=True,
        )

    async def list_by_issue_key(self, jira_issue_key: str, *, limit: int = 20) -> Page[Row]:
        """Historial de un issue concreto, que es lo que alimenta el análisis técnico."""
        return await self.list_page(
            limit=limit,
            filters={"jira_issue_key": jira_issue_key},
            order_column="occurred_at",
            descending=True,
        )
