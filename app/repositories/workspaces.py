"""Acceso a datos de contenedores de trabajo.

Un contenedor es lo que agrupa el trabajo en el sistema de origen: un proyecto en Jira, un
repositorio en GitHub, una base de datos en Notion. El nombre es genérico porque la tabla sirve
a todos los providers.
"""

from __future__ import annotations

from typing import ClassVar

from app.core.exceptions import EntityNotFoundError
from app.repositories.base import BaseRepository, Row
from app.schemas.events import ProviderName


class WorkspaceRepository(BaseRepository):
    """Contenedores de trabajo, identificados por provider y clave."""

    table_name: ClassVar[str] = "workspaces"
    soft_delete: ClassVar[bool] = True

    async def get_by_key(
        self, provider: ProviderName, workspace_key: str
    ) -> Row | None:
        """Devuelve el contenedor por provider y clave, o ``None``.

        La clave sola no basta como identificador: un proyecto ``API`` en Jira y un repositorio
        ``API`` en GitHub son cosas distintas.
        """
        return await self.find_one(
            {"provider": provider.value, "workspace_key": workspace_key}
        )

    async def get_by_key_or_raise(
        self, provider: ProviderName, workspace_key: str
    ) -> Row:
        """Devuelve el contenedor o eleva ``EntityNotFoundError``."""
        row = await self.get_by_key(provider, workspace_key)
        if row is None:
            raise EntityNotFoundError(
                f"El contenedor {workspace_key} de {provider.value} no está registrado.",
                details={"provider": provider.value, "workspace_key": workspace_key},
            )
        return row

    async def ensure(
        self,
        *,
        provider: ProviderName,
        workspace_key: str,
        name: str | None = None,
    ) -> Row:
        """Devuelve el contenedor, creándolo si aún no existe.

        La ingesta no debe fallar porque el contenedor no se haya dado de alta a mano. El coste
        por hora queda a cero, que es lo que hace que el impacto económico salga cero hasta que
        alguien lo configure.
        """
        existing = await self.get_by_key(provider, workspace_key)
        if existing is not None:
            return existing
        return await self.upsert(
            {
                "provider": provider.value,
                "workspace_key": workspace_key,
                "name": name or workspace_key,
            },
            on_conflict="provider,workspace_key",
        )
