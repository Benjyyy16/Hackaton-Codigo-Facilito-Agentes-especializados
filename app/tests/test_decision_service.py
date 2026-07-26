"""Tests del DecisionService: aprobación, rechazo y ejecución de acciones sensibles.

Valida:
- Máquina de estados: solo pending permite transiciones de aprobación.
- Sin aprobación NO hay ejecución (la guarda más importante del sistema).
- Ejecutor que falla -> failed, no propaga.
- Sin ejecutor registrado -> SKIPPED + ActionNotExecutableError.
- Fallos de timeline y difusión NO revierten la decisión.
- Cada transición emite el EventType correcto.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import EntityNotFoundError
from app.schemas.domain import ActionType, ApprovalStatus, ExecutionStatus
from app.services.decision_service import (
    ActionNotExecutableError,
    DecisionService,
    DecisionStateError,
)
from app.websocket.manager import ConnectionManager, EventType, WsEvent


# --- Helpers -------------------------------------------------------------------


def _make_decision_row(
    *,
    approval_status: str = ApprovalStatus.PENDING.value,
    execution_status: str | None = None,
    action_type: str = ActionType.UPDATE_JIRA_ISSUE.value,
    **overrides: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(uuid4()),
        "risk_case_id": str(uuid4()),
        "commitment_id": str(uuid4()),
        "action_type": action_type,
        "title": "Actualizar ticket bloqueante",
        "rationale": "El ticket lleva 5 días sin movimiento",
        "proposed_payload": {"issue_key": "DAT-42", "status": "In Progress"},
        "approval_status": approval_status,
        "execution_status": execution_status,
        "approved_by": None,
        "approved_at": None,
        "execution_result": None,
        "error": None,
    }
    row.update(overrides)
    return row


def _build_service(
    *,
    decision_row: dict[str, Any] | None = None,
    executors: dict[ActionType, Any] | None = None,
    timeline_fails: bool = False,
    broadcast_fails: bool = False,
) -> tuple[DecisionService, dict[str, AsyncMock]]:
    """Construye el servicio con mocks y devuelve los mocks para inspección."""
    decisions = AsyncMock()
    timeline = AsyncMock()
    ws = AsyncMock(spec=ConnectionManager)

    # get_or_raise devuelve la fila o eleva
    if decision_row is not None:
        decisions.get_or_raise.return_value = decision_row
    else:
        decisions.get_or_raise.side_effect = EntityNotFoundError()

    # approve/reject/mark_execution devuelven una fila actualizada por defecto
    def _updated_row(**updates: Any) -> dict[str, Any]:
        base = dict(decision_row or _make_decision_row())
        base.update(updates)
        return base

    decisions.approve.return_value = _updated_row(
        approval_status=ApprovalStatus.APPROVED.value, approved_by="admin"
    )
    decisions.reject.return_value = _updated_row(
        approval_status=ApprovalStatus.REJECTED.value
    )
    decisions.mark_execution = AsyncMock(
        side_effect=lambda did, **kw: _updated_row(**kw)
    )

    if timeline_fails:
        timeline.append.side_effect = RuntimeError("timeline down")
    if broadcast_fails:
        ws.broadcast.side_effect = RuntimeError("ws down")

    svc = DecisionService(
        decisions=decisions,
        timeline=timeline,
        ws_manager=ws,
        executors=executors,
    )
    return svc, {"decisions": decisions, "timeline": timeline, "ws": ws}


# --- Tests: approve ------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_from_pending():
    row = _make_decision_row(approval_status=ApprovalStatus.PENDING.value)
    svc, mocks = _build_service(decision_row=row)
    result = await svc.approve(uuid4(), "admin")
    assert result["approval_status"] == ApprovalStatus.APPROVED.value
    mocks["decisions"].approve.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_from_approved_raises():
    row = _make_decision_row(approval_status=ApprovalStatus.APPROVED.value)
    svc, _ = _build_service(decision_row=row)
    with pytest.raises(DecisionStateError):
        await svc.approve(uuid4(), "admin")


@pytest.mark.asyncio
async def test_approve_from_rejected_raises():
    row = _make_decision_row(approval_status=ApprovalStatus.REJECTED.value)
    svc, _ = _build_service(decision_row=row)
    with pytest.raises(DecisionStateError):
        await svc.approve(uuid4(), "admin")


@pytest.mark.asyncio
async def test_approve_emits_decision_approved():
    row = _make_decision_row()
    svc, mocks = _build_service(decision_row=row)
    await svc.approve(uuid4(), "admin")
    call_args = mocks["ws"].broadcast.call_args[0][0]
    assert call_args.type == EventType.DECISION_APPROVED


# --- Tests: reject -------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_from_pending():
    row = _make_decision_row()
    svc, mocks = _build_service(decision_row=row)
    result = await svc.reject(uuid4(), "cto", "No es prioritario")
    assert result["approval_status"] == ApprovalStatus.REJECTED.value
    mocks["decisions"].reject.assert_awaited_once()


@pytest.mark.asyncio
async def test_reject_from_approved_raises():
    row = _make_decision_row(approval_status=ApprovalStatus.APPROVED.value)
    svc, _ = _build_service(decision_row=row)
    with pytest.raises(DecisionStateError):
        await svc.reject(uuid4(), "cto", "tarde")


@pytest.mark.asyncio
async def test_reject_emits_decision_rejected():
    row = _make_decision_row()
    svc, mocks = _build_service(decision_row=row)
    await svc.reject(uuid4(), "cto", "motivo")
    call_args = mocks["ws"].broadcast.call_args[0][0]
    assert call_args.type == EventType.DECISION_REJECTED


# --- Tests: execute ------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_without_approval_raises():
    """SIN aprobación -> DecisionStateError. Demuestra que no hay puerta trasera."""
    row = _make_decision_row(approval_status=ApprovalStatus.PENDING.value)
    svc, _ = _build_service(decision_row=row)
    with pytest.raises(DecisionStateError, match="no está aprobada"):
        await svc.execute(uuid4(), "operator")


@pytest.mark.asyncio
async def test_execute_rejected_raises():
    """Rechazada tampoco se ejecuta."""
    row = _make_decision_row(approval_status=ApprovalStatus.REJECTED.value)
    svc, _ = _build_service(decision_row=row)
    with pytest.raises(DecisionStateError, match="no está aprobada"):
        await svc.execute(uuid4(), "operator")


@pytest.mark.asyncio
async def test_execute_already_executed_raises():
    row = _make_decision_row(
        approval_status=ApprovalStatus.APPROVED.value,
        execution_status=ExecutionStatus.SUCCEEDED.value,
    )
    svc, _ = _build_service(decision_row=row)
    with pytest.raises(DecisionStateError, match="ya se ejecutó"):
        await svc.execute(uuid4(), "operator")


@pytest.mark.asyncio
async def test_execute_approved_without_executor_raises_skipped():
    """Sin ejecutor registrado -> ActionNotExecutableError y queda SKIPPED."""
    row = _make_decision_row(approval_status=ApprovalStatus.APPROVED.value)
    svc, mocks = _build_service(decision_row=row, executors={})
    with pytest.raises(ActionNotExecutableError):
        await svc.execute(uuid4(), "operator")
    # Verifica que se marcó como SKIPPED
    mark_calls = mocks["decisions"].mark_execution.call_args_list
    assert any(
        call.kwargs.get("status") == ExecutionStatus.SKIPPED.value
        for call in mark_calls
    )


@pytest.mark.asyncio
async def test_execute_approved_with_executor_succeeds():
    row = _make_decision_row(
        approval_status=ApprovalStatus.APPROVED.value,
        action_type=ActionType.UPDATE_JIRA_ISSUE.value,
    )
    executor = AsyncMock(return_value={"updated": True})
    svc, mocks = _build_service(
        decision_row=row,
        executors={ActionType.UPDATE_JIRA_ISSUE: executor},
    )
    result = await svc.execute(uuid4(), "operator")
    assert result.get("status") == ExecutionStatus.SUCCEEDED.value
    executor.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_emits_decision_executed():
    row = _make_decision_row(
        approval_status=ApprovalStatus.APPROVED.value,
        action_type=ActionType.UPDATE_JIRA_ISSUE.value,
    )
    executor = AsyncMock(return_value={"done": True})
    svc, mocks = _build_service(
        decision_row=row,
        executors={ActionType.UPDATE_JIRA_ISSUE: executor},
    )
    await svc.execute(uuid4(), "op")
    call_args = mocks["ws"].broadcast.call_args[0][0]
    assert call_args.type == EventType.DECISION_EXECUTED


@pytest.mark.asyncio
async def test_executor_raises_marks_failed_no_propagation():
    """Ejecutor que eleva -> failed con error, NO propaga la excepción."""
    row = _make_decision_row(
        approval_status=ApprovalStatus.APPROVED.value,
        action_type=ActionType.UPDATE_JIRA_ISSUE.value,
    )
    executor = AsyncMock(side_effect=RuntimeError("jira timeout"))
    svc, mocks = _build_service(
        decision_row=row,
        executors={ActionType.UPDATE_JIRA_ISSUE: executor},
    )
    # No propaga
    result = await svc.execute(uuid4(), "op")
    # Se marcó como failed
    mark_calls = mocks["decisions"].mark_execution.call_args_list
    assert any(
        call.kwargs.get("status") == ExecutionStatus.FAILED.value
        for call in mark_calls
    )
    assert any(
        "RuntimeError" in (call.kwargs.get("error") or "")
        for call in mark_calls
    )


# --- Tests: resiliencia --------------------------------------------------------


@pytest.mark.asyncio
async def test_timeline_failure_does_not_revert_approval():
    """Fallo al anotar cronología NO revierte la decisión."""
    row = _make_decision_row()
    svc, mocks = _build_service(decision_row=row, timeline_fails=True)
    # No eleva
    result = await svc.approve(uuid4(), "admin")
    assert result["approval_status"] == ApprovalStatus.APPROVED.value


@pytest.mark.asyncio
async def test_broadcast_failure_does_not_revert_decision():
    """Fallo de difusión NO revierte la decisión."""
    row = _make_decision_row()
    svc, mocks = _build_service(decision_row=row, broadcast_fails=True)
    result = await svc.approve(uuid4(), "admin")
    assert result["approval_status"] == ApprovalStatus.APPROVED.value


@pytest.mark.asyncio
async def test_timeline_failure_does_not_revert_execution():
    """Fallo de timeline durante ejecución NO revierte."""
    row = _make_decision_row(
        approval_status=ApprovalStatus.APPROVED.value,
        action_type=ActionType.UPDATE_JIRA_ISSUE.value,
    )
    executor = AsyncMock(return_value={"ok": True})
    svc, mocks = _build_service(
        decision_row=row,
        executors={ActionType.UPDATE_JIRA_ISSUE: executor},
        timeline_fails=True,
    )
    result = await svc.execute(uuid4(), "op")
    assert result.get("status") == ExecutionStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_broadcast_failure_does_not_revert_execution():
    """Fallo de WS durante ejecución NO revierte."""
    row = _make_decision_row(
        approval_status=ApprovalStatus.APPROVED.value,
        action_type=ActionType.UPDATE_JIRA_ISSUE.value,
    )
    executor = AsyncMock(return_value={"ok": True})
    svc, mocks = _build_service(
        decision_row=row,
        executors={ActionType.UPDATE_JIRA_ISSUE: executor},
        broadcast_fails=True,
    )
    result = await svc.execute(uuid4(), "op")
    assert result.get("status") == ExecutionStatus.SUCCEEDED.value


# --- Tests: decision no encontrada ---------------------------------------------


@pytest.mark.asyncio
async def test_approve_nonexistent_decision_raises():
    svc, _ = _build_service(decision_row=None)
    with pytest.raises(EntityNotFoundError):
        await svc.approve(uuid4(), "admin")


@pytest.mark.asyncio
async def test_reject_nonexistent_decision_raises():
    svc, _ = _build_service(decision_row=None)
    with pytest.raises(EntityNotFoundError):
        await svc.reject(uuid4(), "cto", "motivo")


@pytest.mark.asyncio
async def test_execute_nonexistent_decision_raises():
    svc, _ = _build_service(decision_row=None)
    with pytest.raises(EntityNotFoundError):
        await svc.execute(uuid4(), "op")
