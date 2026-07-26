"""Acceso a datos de compromisos."""

from __future__ import annotations

from typing import Any, ClassVar
from uuid import UUID

from app.repositories.base import BaseRepository, Page, Row


class CommitmentRepository(BaseRepository):
    """Compromisos derivados de issues de Jira."""

    table_name: ClassVar[str] = "commitments"
    soft_delete: ClassVar[bool] = True

    async def get_by_issue_key(self, project_id: UUID, jira_issue_key: str) -> Row | None:
        """Devuelve el compromiso de un issue dentro de un proyecto."""
        return await self.find_one(
            {"project_id": str(project_id), "jira_issue_key": jira_issue_key}
        )

    async def upsert_from_issue(
        self,
        *,
        project_id: UUID,
        jira_issue_key: str,
        title: str,
        due_date: str | None = None,
        estimated_hours: float | None = None,
        status: str | None = None,
    ) -> Row:
        """Crea o actualiza el compromiso que representa un issue.

        Se apoya en la restricción ``unique (project_id, jira_issue_key)`` del esquema, de
        modo que reprocesar el mismo issue actualiza en lugar de duplicar.

        Los valores ``None`` se omiten a propósito: un payload de Jira que no trae la fecha
        de vencimiento no debe borrar la que ya estaba registrada.
        """
        payload: dict[str, Any] = {
            "project_id": str(project_id),
            "jira_issue_key": jira_issue_key,
            "title": title,
        }
        if due_date is not None:
            payload["due_date"] = due_date
        if estimated_hours is not None:
            payload["estimated_hours"] = estimated_hours
        if status is not None:
            payload["status"] = status

        return await self.upsert(payload, on_conflict="project_id,jira_issue_key")

    async def set_status(self, commitment_id: UUID, status: str) -> Row:
        """Actualiza el estado del compromiso."""
        return await self.update(commitment_id, {"status": status})

    async def list_by_project(
        self, project_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> Page[Row]:
        """Lista los compromisos vivos de un proyecto."""
        return await self.list_page(
            limit=limit,
            offset=offset,
            filters={"project_id": str(project_id)},
        )
