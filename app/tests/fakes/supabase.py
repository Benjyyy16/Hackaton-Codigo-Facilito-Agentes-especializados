"""Doble del cliente asíncrono de Supabase.

Los tests no tocan la red ni una instancia real (RNF-4.2). Este doble imita el encadenado de
``postgrest`` y registra cada eslabón, de modo que un test pueda afirmar sobre la consulta
que se construyó y no solo sobre lo que devolvió. Ahí es donde se detectan los fallos que
importan: un filtro de borrado lógico ausente o un rango de paginación mal calculado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from postgrest.exceptions import APIError


@dataclass
class RecordedCall:
    """Un eslabón de la cadena, con su nombre y argumentos."""

    method: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuración
        return f"{self.method}(args={self.args}, kwargs={self.kwargs})"


@dataclass
class FakeResponse:
    """Equivalente a ``APIResponse``: datos y recuento."""

    data: list[dict[str, Any]] = field(default_factory=list)
    count: int | None = None


class FakeQuery:
    """Constructor de consultas que acumula llamadas y devuelve una respuesta preparada."""

    def __init__(self, table: FakeTable) -> None:
        self._table = table

    def _record(self, method: str, *args: Any, **kwargs: Any) -> FakeQuery:
        self._table.calls.append(RecordedCall(method, args, kwargs))
        return self

    # El encadenado de postgrest: cada método devuelve el propio constructor.
    def select(self, *args: Any, **kwargs: Any) -> FakeQuery:
        return self._record("select", *args, **kwargs)

    def insert(self, *args: Any, **kwargs: Any) -> FakeQuery:
        return self._record("insert", *args, **kwargs)

    def update(self, *args: Any, **kwargs: Any) -> FakeQuery:
        return self._record("update", *args, **kwargs)

    def upsert(self, *args: Any, **kwargs: Any) -> FakeQuery:
        return self._record("upsert", *args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> FakeQuery:
        return self._record("delete", *args, **kwargs)

    def eq(self, column: str, value: Any) -> FakeQuery:
        return self._record("eq", column, value)

    def is_(self, column: str, value: Any) -> FakeQuery:
        return self._record("is_", column, value)

    def order(self, column: str, **kwargs: Any) -> FakeQuery:
        return self._record("order", column, **kwargs)

    def range(self, start: int, end: int) -> FakeQuery:
        return self._record("range", start, end)

    def limit(self, size: int) -> FakeQuery:
        return self._record("limit", size)

    async def execute(self) -> FakeResponse:
        self._table.calls.append(RecordedCall("execute"))
        if self._table.error is not None:
            raise self._table.error
        return self._table.response


class FakeTable:
    """Respuesta o error preparados para una tabla, más el registro de llamadas."""

    def __init__(self) -> None:
        self.response = FakeResponse()
        self.error: Exception | None = None
        self.calls: list[RecordedCall] = []

    def returns(
        self, rows: list[dict[str, Any]], *, count: int | None = None
    ) -> FakeTable:
        self.response = FakeResponse(data=rows, count=count)
        self.error = None
        return self

    def raises(self, error: Exception) -> FakeTable:
        self.error = error
        return self

    def raises_api_error(self, code: str, message: str = "error") -> FakeTable:
        """Prepara un ``APIError`` de ``postgrest`` con el código indicado."""
        return self.raises(
            APIError({"code": code, "message": message, "details": None, "hint": None})
        )

    # --- Consultas sobre lo registrado --------------------------------------------

    def methods(self) -> list[str]:
        return [call.method for call in self.calls]

    def calls_to(self, method: str) -> list[RecordedCall]:
        return [call for call in self.calls if call.method == method]

    def called(self, method: str) -> bool:
        return any(call.method == method for call in self.calls)

    def payload(self) -> dict[str, Any]:
        """Primer argumento de la última escritura registrada."""
        for call in reversed(self.calls):
            if call.method in {"insert", "update", "upsert"} and call.args:
                return call.args[0]
        raise AssertionError("No se registró ninguna escritura")


class FakeSupabaseClient:
    """Doble de ``AsyncClient`` limitado a ``table()``."""

    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}

    def for_table(self, name: str) -> FakeTable:
        """Devuelve el doble de una tabla, creándolo si hace falta."""
        return self.tables.setdefault(name, FakeTable())

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self.for_table(name))
