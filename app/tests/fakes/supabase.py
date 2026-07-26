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


def _api_error(code: str, message: str = "error") -> APIError:
    """Construye un ``APIError`` de ``postgrest`` con el código indicado."""
    return APIError({"code": code, "message": message, "details": None, "hint": None})


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

    def contains(self, column: str, value: Any) -> FakeQuery:
        """Operador de contención de JSONB (``cs``)."""
        return self._record("contains", column, value)

    def in_(self, column: str, values: Any) -> FakeQuery:
        return self._record("in_", column, values)

    def ilike(self, column: str, pattern: str) -> FakeQuery:
        return self._record("ilike", column, pattern)

    def gte(self, column: str, value: Any) -> FakeQuery:
        return self._record("gte", column, value)

    def lte(self, column: str, value: Any) -> FakeQuery:
        return self._record("lte", column, value)

    def neq(self, column: str, value: Any) -> FakeQuery:
        return self._record("neq", column, value)

    def not_(self, *args: Any, **kwargs: Any) -> FakeQuery:
        return self._record("not_", *args, **kwargs)

    def text_search(self, column: str, query: str, **kwargs: Any) -> FakeQuery:
        return self._record("text_search", column, query, **kwargs)

    async def execute(self) -> FakeResponse:
        self._table.calls.append(RecordedCall("execute"))
        return self._table.next_outcome()


class FakeTable:
    """Respuestas preparadas para una tabla, más el registro de llamadas.

    Admite dos modos. El habitual es una respuesta fija con ``returns``. Cuando un escenario
    necesita respuestas distintas en llamadas sucesivas sobre la misma tabla (por ejemplo, una
    búsqueda que no encuentra nada seguida de una inserción que devuelve la fila creada), se
    encolan con ``then``. Sin esa distinción, un flujo de lectura y escritura sobre la misma
    tabla no se puede representar.
    """

    def __init__(self) -> None:
        self.response = FakeResponse()
        self.error: Exception | None = None
        self.calls: list[RecordedCall] = []
        self._queue: list[FakeResponse | Exception] = []

    def returns(
        self, rows: list[dict[str, Any]], *, count: int | None = None
    ) -> FakeTable:
        """Fija la respuesta por defecto, usada cuando la cola está vacía."""
        self.response = FakeResponse(data=rows, count=count)
        self.error = None
        return self

    def then(self, rows: list[dict[str, Any]], *, count: int | None = None) -> FakeTable:
        """Encola la respuesta de la siguiente ejecución."""
        self._queue.append(FakeResponse(data=rows, count=count))
        return self

    def then_raises(self, error: Exception) -> FakeTable:
        """Encola un fallo para la siguiente ejecución."""
        self._queue.append(error)
        return self

    def then_raises_api_error(self, code: str, message: str = "error") -> FakeTable:
        """Encola un ``APIError`` de ``postgrest`` con el código indicado."""
        return self.then_raises(_api_error(code, message))

    def raises(self, error: Exception) -> FakeTable:
        self.error = error
        return self

    def raises_api_error(self, code: str, message: str = "error") -> FakeTable:
        """Prepara un ``APIError`` de ``postgrest`` con el código indicado."""
        return self.raises(_api_error(code, message))

    def next_outcome(self) -> FakeResponse:
        """Devuelve la respuesta que corresponde a esta ejecución, o eleva el fallo."""
        if self._queue:
            outcome = self._queue.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        if self.error is not None:
            raise self.error
        return self.response

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
