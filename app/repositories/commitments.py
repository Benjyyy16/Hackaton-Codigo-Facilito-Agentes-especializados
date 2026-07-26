"""Acceso a datos de compromisos."""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from app.repositories.base import BaseRepository, Page, Row


class CommitmentRepository(BaseRepository):
    """Compromisos derivados de elementos de trabajo de cualquier provider."""

    table_name: ClassVar[str] = "commitments"
    soft_delete: ClassVar[bool] = True

    async def get_by_issue_key(self, workspace_id: UUID, external_key: str) -> Row | None:
        """Devuelve el compromiso de un elemento dentro de un contenedor."""
        return await self.find_one(
            {"workspace_id": str(workspace_id), "external_key": external_key}
        )

    async def upsert_from_issue(
        self,
        *,
        workspace_id: UUID,
        provider: str,
        external_key: str,
        title: str,
        due_date: str | None = None,
        estimated_hours: float | None = None,
        status: str | None = None,
    ) -> Row:
        """Crea o actualiza el compromiso que representa un elemento de trabajo.

        Se apoya en la restricción ``unique (workspace_id, external_key)`` del esquema, de
        modo que reprocesar el mismo elemento actualiza en lugar de duplicar.

        Los valores ``None`` se omiten a propósito: un payload que no trae la fecha
        de vencimiento no debe borrar la que ya estaba registrada.
        """
        payload: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "provider": provider,
            "external_key": external_key,
            "title": title,
        }
        if due_date is not None:
            payload["due_date"] = due_date
        if estimated_hours is not None:
            payload["estimated_hours"] = estimated_hours
        if status is not None:
            payload["status"] = status

        return await self.upsert(payload, on_conflict="workspace_id,external_key")

    async def set_status(self, commitment_id: UUID, status: str) -> Row:
        """Actualiza el estado del compromiso."""
        return await self.update(commitment_id, {"status": status})

    async def list_by_workspace(
        self, workspace_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> Page[Row]:
        """Lista los compromisos vivos de un contenedor."""
        return await self.list_page(
            limit=limit,
            offset=offset,
            filters={"workspace_id": str(workspace_id)},
        )
