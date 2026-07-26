"""Servicio de decisiones: aprobación humana de acciones sensibles.

El backend propone; una persona decide. Este servicio es el único camino por el que una
acción propuesta puede llegar a ejecutarse, y su regla central es simple: sin aprobación
no hay ejecución.

La regla vive en tres sitios a propósito, y no por redundancia descuidada:

1. Aquí, para dar un error de dominio con mensaje útil.
2. En la restricción ``check`` de la tabla ``decisions``, para que ninguna ruta futura
   pueda saltarse el servicio.
3. En el registro de ejecutores, que está vacío para las acciones que aún no tienen
   implementación segura.

El tercero es el que evita el fallo más peligroso: aprobar algo que el sistema no sabe
ejecutar y marcarlo como hecho.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable
from uuid import UUID

from app.core.exceptions import DomainError
from app.core.logging import get_logger
from app.repositories.domain import DecisionRepository, TimelineRepository
from app.schemas.domain import ActionType, ApprovalStatus, ExecutionStatus
from app.websocket.manager import ConnectionManager, EventType, WsEvent

logger = get_logger("service.decisions")


class DecisionStateError(DomainError):
    """La decisión no está en un estado que admita la operación pedida."""


class ActionNotExecutableError(DomainError):
    """La acción está aprobada pero el sistema no tiene un ejecutor seguro para ella."""


#: Ejecutor de una acción aprobada. Recibe el payload propuesto y devuelve el resultado.
Executor = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class DecisionService:
    """Gestiona el ciclo de vida de las decisiones."""

    def __init__(
        self,
        *,
        decisions: DecisionRepository,
        timeline: TimelineRepository,
        ws_manager: ConnectionManager,
        executors: dict[ActionType, Executor] | None = None,
    ) -> None:
        self._decisions = decisions
        self._timeline = timeline
        self._ws = ws_manager
        # Registro de ejecutores. Deliberadamente vacío por defecto: una acción sin
        # ejecutor registrado se rechaza al intentar ejecutarla, en lugar de marcarse
        # como hecha sin haber ocurrido. Registrar un ejecutor es una decisión explícita.
        self._executors: dict[ActionType, Executor] = executors or {}

    # --- Aprobación ----------------------------------------------------------------

    async def approve(self, decision_id: UUID, approved_by: str) -> dict[str, Any]:
        """Aprueba una decisión pendiente.

        Solo desde ``pending``: reaprobar una decisión ya aprobada o rechazada
        reescribiría la auditoría, que es justo lo que la auditoría existe para evitar.
        """
        row = await self._decisions.get_or_raise(decision_id)
        current = row.get("approval_status")

        if current != ApprovalStatus.PENDING.value:
            raise DecisionStateError(
                f"La decisión ya está en estado '{current}': solo se puede aprobar una pendiente.",
                details={"decision_id": str(decision_id), "approval_status": current},
            )

        updated = await self._decisions.approve(decision_id, approved_by)
        await self._record(updated, "decision.approved", f"Aprobada por {approved_by}", approved_by)
        await self._broadcast(EventType.DECISION_APPROVED, updated)
        return updated

    async def reject(
        self, decision_id: UUID, rejected_by: str, reason: str
    ) -> dict[str, Any]:
        """Rechaza una decisión pendiente, dejando el motivo registrado."""
        row = await self._decisions.get_or_raise(decision_id)
        current = row.get("approval_status")

        if current != ApprovalStatus.PENDING.value:
            raise DecisionStateError(
                f"La decisión ya está en estado '{current}': solo se puede rechazar una pendiente.",
                details={"decision_id": str(decision_id), "approval_status": current},
            )

        updated = await self._decisions.reject(decision_id, rejected_by, reason)
        await self._record(
            updated, "decision.rejected", f"Rechazada por {rejected_by}: {reason}", rejected_by
        )
        await self._broadcast(EventType.DECISION_REJECTED, updated)
        return updated

    # --- Ejecución -----------------------------------------------------------------

    async def execute(self, decision_id: UUID, executed_by: str) -> dict[str, Any]:
        """Ejecuta una decisión aprobada.

        Cuatro guardas antes de tocar nada:

        1. La decisión existe.
        2. Está aprobada. Sin esto, el endpoint de ejecución sería una puerta trasera que
           evita la aprobación.
        3. No se ejecutó ya. Reejecutar una acción idempotente es inocuo; reejecutar una
           que no lo es duplica el efecto.
        4. Hay un ejecutor registrado para su tipo. Sin esto, aprobar algo que el sistema
           no sabe hacer lo dejaría marcado como hecho.
        """
        row = await self._decisions.get_or_raise(decision_id)

        if row.get("approval_status") != ApprovalStatus.APPROVED.value:
            raise DecisionStateError(
                "La decisión no está aprobada: no se puede ejecutar.",
                details={
                    "decision_id": str(decision_id),
                    "approval_status": row.get("approval_status"),
                },
            )

        if row.get("execution_status") not in {None, ExecutionStatus.NOT_STARTED.value}:
            raise DecisionStateError(
                f"La decisión ya se ejecutó (estado '{row.get('execution_status')}').",
                details={"decision_id": str(decision_id)},
            )

        action_type = ActionType(row["action_type"])
        executor = self._executors.get(action_type)

        if executor is None:
            # Se marca como omitida, no como fallida: no hubo un fallo de ejecución, es
            # que no existe ejecución posible. La distinción importa al leer la auditoría.
            await self._decisions.mark_execution(
                decision_id,
                status=ExecutionStatus.SKIPPED.value,
                result={"reason": "sin ejecutor registrado"},
            )
            raise ActionNotExecutableError(
                f"No hay ejecutor registrado para '{action_type.value}'. "
                "La acción queda aprobada y pendiente de ejecución manual.",
                details={"action_type": action_type.value},
            )

        await self._decisions.mark_execution(
            decision_id, status=ExecutionStatus.RUNNING.value
        )

        try:
            result = await executor(row.get("proposed_payload") or {})
        except Exception as error:  # noqa: BLE001 - frontera con el sistema externo
            logger.error(
                "La ejecución de la decisión %s falló", decision_id, exc_info=error
            )
            updated = await self._decisions.mark_execution(
                decision_id,
                status=ExecutionStatus.FAILED.value,
                error=f"{type(error).__name__}: {error}",
            )
            await self._record(
                updated,
                "decision.execution_failed",
                f"La ejecución falló: {type(error).__name__}",
                executed_by,
            )
            await self._broadcast(EventType.DECISION_EXECUTED, updated)
            return updated

        updated = await self._decisions.mark_execution(
            decision_id, status=ExecutionStatus.SUCCEEDED.value, result=result
        )
        await self._record(
            updated, "decision.executed", f"Ejecutada por {executed_by}", executed_by
        )
        await self._broadcast(EventType.DECISION_EXECUTED, updated)
        return updated

    # --- Auditoría y difusión ------------------------------------------------------

    async def _record(
        self, row: dict[str, Any], event_type: str, summary: str, actor: str
    ) -> None:
        """Anota el cambio en la cronología del compromiso.

        Un fallo al anotar no revierte la decisión: la fila de ``decisions`` ya es el
        registro autoritativo, y la cronología es una vista legible construida sobre él.
        """
        commitment_id = row.get("commitment_id")
        if not commitment_id:
            return
        try:
            await self._timeline.append(
                commitment_id=UUID(commitment_id),
                actor_type="human",
                actor_name=actor,
                event_type=event_type,
                summary=summary,
                payload={
                    "decision_id": row.get("id"),
                    "action_type": row.get("action_type"),
                    "approval_status": row.get("approval_status"),
                    "execution_status": row.get("execution_status"),
                },
            )
        except Exception as error:  # noqa: BLE001 - la cronología no es autoritativa
            logger.warning("No se pudo anotar en la cronología: %s", type(error).__name__)

    async def _broadcast(self, event_type: EventType, row: dict[str, Any]) -> None:
        try:
            await self._ws.broadcast(
                WsEvent(
                    type=event_type,
                    commitment_id=(
                        UUID(row["commitment_id"]) if row.get("commitment_id") else None
                    ),
                    risk_case_id=(
                        UUID(row["risk_case_id"]) if row.get("risk_case_id") else None
                    ),
                    data={
                        "decision_id": row.get("id"),
                        "action_type": row.get("action_type"),
                        "approval_status": row.get("approval_status"),
                        "execution_status": row.get("execution_status"),
                        "approved_by": row.get("approved_by"),
                    },
                )
            )
        except Exception as error:  # noqa: BLE001 - la difusión no es crítica
            logger.warning("Difusión fallida: %s", type(error).__name__)
