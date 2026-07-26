"""Rutas de decisiones (aprobación humana)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import DecisionServiceDep, DomainRepositoriesDep
from app.schemas.domain import DecisionApprove, DecisionRead, DecisionReject
from app.services.decision_service import ActionNotExecutableError, DecisionStateError

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get(
    "",
    response_model=list[DecisionRead],
    summary="Listar decisiones",
    description="Lista paginada de decisiones con filtro opcional por approval_status.",
)
async def list_decisions(
    repos: DomainRepositoriesDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    approval_status: str | None = Query(default=None),
) -> list[DecisionRead]:
    filters: dict[str, str] = {}
    if approval_status:
        filters["approval_status"] = approval_status
    page = await repos.decisions.list_page(limit=limit, offset=offset, filters=filters)
    return [DecisionRead.model_validate(row) for row in page.items]


@router.post(
    "/{decision_id}/approve",
    response_model=DecisionRead,
    summary="Aprobar decisión",
    description="Aprueba una decisión pendiente. 409 si ya no está pendiente.",
)
async def approve_decision(
    decision_id: UUID,
    body: DecisionApprove,
    service: DecisionServiceDep,
) -> DecisionRead:
    try:
        row = await service.approve(decision_id, body.approved_by)
    except DecisionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return DecisionRead.model_validate(row)


@router.post(
    "/{decision_id}/reject",
    response_model=DecisionRead,
    summary="Rechazar decisión",
    description="Rechaza una decisión pendiente con motivo. 409 si ya no está pendiente.",
)
async def reject_decision(
    decision_id: UUID,
    body: DecisionReject,
    service: DecisionServiceDep,
) -> DecisionRead:
    try:
        row = await service.reject(decision_id, body.rejected_by, body.reason)
    except DecisionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return DecisionRead.model_validate(row)


@router.post(
    "/{decision_id}/execute",
    response_model=DecisionRead,
    summary="Ejecutar decisión aprobada",
    description=(
        "Ejecuta una decisión previamente aprobada. "
        "409 si no está aprobada. 422 si no hay ejecutor registrado."
    ),
)
async def execute_decision(
    decision_id: UUID,
    service: DecisionServiceDep,
) -> DecisionRead:
    try:
        row = await service.execute(decision_id, executed_by="api-user")
    except DecisionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    except ActionNotExecutableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message
        ) from exc
    return DecisionRead.model_validate(row)
