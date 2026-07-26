"""Acceso a datos de proyectos."""

from __future__ import annotations

from typing import ClassVar

from app.core.exceptions import EntityNotFoundError
from app.repositories.base import BaseRepository, Row


class ProjectRepository(BaseRepository):
    """Proyectos, identificados de cara a Jira por su clave de proyecto."""

    table_name: ClassVar[str] = "projects"
    soft_delete: ClassVar[bool] = True

    async def get_by_jira_key(self, jira_project_key: str) -> Row | None:
        """Devuelve el proyecto por su clave de Jira, o ``None``."""
        return await self.find_one({"jira_project_key": jira_project_key})

    async def get_by_jira_key_or_raise(self, jira_project_key: str) -> Row:
        """Devuelve el proyecto por su clave de Jira o eleva ``EntityNotFoundError``."""
        row = await self.get_by_jira_key(jira_project_key)
        if row is None:
            raise EntityNotFoundError(
                f"El proyecto {jira_project_key} no está registrado.",
                details={"jira_project_key": jira_project_key},
            )
        return row

    async def ensure(self, *, jira_project_key: str, name: str | None = None) -> Row:
        """Devuelve el proyecto, creándolo si aún no existe.

        La ingesta de eventos no debe fallar porque el proyecto no se haya dado de alta a
        mano. El coste por hora queda a cero, que es lo que hace que el impacto económico
        salga cero hasta que alguien lo configure.
        """
        existing = await self.get_by_jira_key(jira_project_key)
        if existing is not None:
            return existing
        return await self.upsert(
            {"jira_project_key": jira_project_key, "name": name or jira_project_key},
            on_conflict="jira_project_key",
        )
