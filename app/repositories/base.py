"""Repositorio base.

Este módulo y sus subclases son el único lugar del proyecto donde aparece
``client.table(...)``. Los servicios acceden a los datos exclusivamente a través de
repositorios (RF-7.2).

Concentra tres comportamientos que, dejados a criterio de quien llama, se olvidan:

* la exclusión de los registros con borrado lógico en toda lectura (RF-7.4);
* la traducción de errores de ``postgrest`` a errores de dominio (RF-7.5);
* la paginación con recuento exacto.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar, Final, Generic, TypeVar
from uuid import UUID

from postgrest.exceptions import APIError
from supabase import AsyncClient

from app.core.exceptions import DuplicateEventError, EntityNotFoundError, SupabaseError
from app.core.logging import get_logger

logger = get_logger("repository")

Row = dict[str, Any]
ModelT = TypeVar("ModelT")

#: Violación de restricción de unicidad en PostgreSQL. La deduplicación depende de tratarlo
#: como duplicado y no como fallo (RF-6.4).
UNIQUE_VIOLATION: Final[str] = "23505"

#: Violación de clave ajena.
FOREIGN_KEY_VIOLATION: Final[str] = "23503"

#: Límite superior de página. Evita que un cliente pida un rango arbitrariamente grande.
MAX_PAGE_SIZE: Final[int] = 100


class Page(Generic[ModelT]):
    """Resultado paginado con el total de coincidencias."""

    __slots__ = ("items", "limit", "offset", "total")

    def __init__(
        self, items: list[ModelT], total: int, *, limit: int, offset: int
    ) -> None:
        self.items = items
        self.total = total
        self.limit = limit
        self.offset = offset

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return (
            f"Page(items={len(self.items)}, total={self.total}, "
            f"limit={self.limit}, offset={self.offset})"
        )


def _utc_now_iso() -> str:
    """Instante actual en ISO 8601 con zona, apto para ``timestamptz``."""
    return datetime.now(UTC).isoformat()


class BaseRepository:
    """Operaciones comunes sobre una tabla de Supabase.

    Las subclases declaran ``table_name`` y, si procede, ``soft_delete``, y añaden solo sus
    consultas propias.
    """

    table_name: ClassVar[str]
    #: Cuando es ``True``, toda lectura excluye los registros con ``deleted_at``.
    soft_delete: ClassVar[bool] = False
    #: Columna de orden por defecto para los listados.
    default_order_column: ClassVar[str] = "created_at"

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    # --- Utilidades internas ------------------------------------------------------

    def _table(self) -> Any:
        return self._client.table(self.table_name)

    def _translate(self, error: APIError) -> Exception:
        """Convierte un error de ``postgrest`` en un error de dominio.

        El código de la violación de unicidad es el que importa: sin esta traducción, la
        deduplicación tendría que inspeccionar excepciones de la librería en las capas
        superiores.
        """
        code = getattr(error, "code", None)
        if code == UNIQUE_VIOLATION:
            return DuplicateEventError(details={"table": self.table_name})
        if code == FOREIGN_KEY_VIOLATION:
            return EntityNotFoundError(
                "La entidad referenciada no existe.",
                details={"table": self.table_name},
            )
        logger.error(
            "Error de Supabase en %s (code=%s)", self.table_name, code, exc_info=error
        )
        return SupabaseError(details={"table": self.table_name})

    def _apply_soft_delete_filter(self, query: Any) -> Any:
        if self.soft_delete:
            return query.is_("deleted_at", "null")
        return query

    @staticmethod
    def _apply_filters(query: Any, filters: dict[str, Any] | None) -> Any:
        """Aplica igualdades simples, ignorando los valores ``None``.

        Ignorar ``None`` permite que las rutas pasen sus parámetros opcionales tal cual, sin
        construir el diccionario condicionalmente en cada caso.
        """
        for column, value in (filters or {}).items():
            if value is not None:
                query = query.eq(column, value)
        return query

    async def _execute(self, query: Any) -> Any:
        try:
            return await query.execute()
        except APIError as error:
            raise self._translate(error) from error
        except Exception as error:  # noqa: BLE001 - frontera con librería externa
            logger.error("Fallo inesperado en %s", self.table_name, exc_info=error)
            raise SupabaseError(details={"table": self.table_name}) from error

    # --- Escritura ----------------------------------------------------------------

    async def create(self, payload: Row) -> Row:
        """Inserta una fila y devuelve la versión persistida."""
        response = await self._execute(self._table().insert(payload))
        rows = response.data or []
        if not rows:
            # PostgREST devuelve la fila insertada salvo que se pida lo contrario. No
            # recibirla significa que la escritura no se confirmó.
            raise SupabaseError(
                "La inserción no devolvió la fila creada.",
                details={"table": self.table_name},
            )
        return rows[0]

    async def update(self, entity_id: UUID, payload: Row) -> Row:
        """Actualiza una fila por identificador.

        ``updated_at`` lo mantiene un trigger en la base de datos, así que no se envía desde
        aquí.
        """
        query = self._apply_soft_delete_filter(
            self._table().update(payload).eq("id", str(entity_id))
        )
        response = await self._execute(query)
        rows = response.data or []
        if not rows:
            raise EntityNotFoundError(details={"table": self.table_name})
        return rows[0]

    async def upsert(self, payload: Row, *, on_conflict: str) -> Row:
        """Inserta o actualiza según la restricción indicada."""
        response = await self._execute(
            self._table().upsert(payload, on_conflict=on_conflict)
        )
        rows = response.data or []
        if not rows:
            raise SupabaseError(
                "El upsert no devolvió la fila resultante.",
                details={"table": self.table_name},
            )
        return rows[0]

    async def soft_delete_by_id(self, entity_id: UUID) -> Row:
        """Marca la fila como borrada sin eliminarla."""
        if not self.soft_delete:
            raise SupabaseError(
                f"La tabla {self.table_name} no admite borrado lógico.",
                details={"table": self.table_name},
            )
        return await self.update(entity_id, {"deleted_at": _utc_now_iso()})

    # --- Lectura ------------------------------------------------------------------

    async def get(self, entity_id: UUID) -> Row | None:
        """Devuelve una fila por identificador, o ``None`` si no existe."""
        query = self._apply_soft_delete_filter(
            self._table().select("*").eq("id", str(entity_id))
        )
        response = await self._execute(query.limit(1))
        rows = response.data or []
        return rows[0] if rows else None

    async def get_or_raise(self, entity_id: UUID) -> Row:
        """Devuelve una fila por identificador o eleva ``EntityNotFoundError``."""
        row = await self.get(entity_id)
        if row is None:
            raise EntityNotFoundError(details={"id": str(entity_id)})
        return row

    async def find_one(self, filters: Row) -> Row | None:
        """Devuelve la primera fila que cumple las igualdades dadas."""
        query = self._apply_soft_delete_filter(self._table().select("*"))
        query = self._apply_filters(query, filters)
        response = await self._execute(query.limit(1))
        rows = response.data or []
        return rows[0] if rows else None

    async def exists(self, filters: Row) -> bool:
        """Indica si existe alguna fila que cumpla las igualdades dadas."""
        return await self.find_one(filters) is not None

    async def list_page(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        filters: Row | None = None,
        order_column: str | None = None,
        descending: bool = True,
    ) -> Page[Row]:
        """Devuelve una página de filas con el total de coincidencias.

        El recuento exacto lo pide ``count="exact"``, y ``range`` es inclusivo en ambos
        extremos, de ahí el ``- 1``.
        """
        safe_limit = max(1, min(limit, MAX_PAGE_SIZE))
        safe_offset = max(0, offset)

        query = self._table().select("*", count="exact")
        query = self._apply_soft_delete_filter(query)
        query = self._apply_filters(query, filters)
        query = query.order(
            order_column or self.default_order_column, desc=descending
        ).range(safe_offset, safe_offset + safe_limit - 1)

        response = await self._execute(query)
        rows = response.data or []
        total = response.count if response.count is not None else len(rows)
        return Page(rows, total, limit=safe_limit, offset=safe_offset)
