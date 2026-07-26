"""Rutas de casos de riesgo."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api.deps import AnalysisServiceDep, DomainRepositoriesDep
from app.schemas.domain import RiskCaseRead

router = APIRouter(prefix="/risk-cases", tags=["risk-cases"])


@router.get(
    "",
    response_model=list[RiskCaseRead],
    summary="Listar casos de riesgo",
    description="Devuelve una lista paginada de casos de riesgo.",
)
async def list_risk_cases(
    repos: DomainRepositoriesDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[RiskCaseRead]:
    page = await repos.risk_cases.list_page(limit=limit, offset=offset)
    return [RiskCaseRead.model_validate(row) for row in page.items]


@router.get(
    "/{risk_case_id}",
    response_model=RiskCaseRead,
    summary="Obtener caso de riesgo",
    description="Devuelve un caso de riesgo por ID. 404 si no existe.",
)
async def get_risk_case(
    risk_case_id: UUID,
    repos: DomainRepositoriesDep,
) -> RiskCaseRead:
    row = await repos.risk_cases.get_or_raise(risk_case_id)
    return RiskCaseRead.model_validate(row)


@router.post(
    "/{risk_case_id}/reanalyze",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reanalizar caso de riesgo",
    description="Dispara un nuevo análisis del compromiso asociado al caso.",
)
async def reanalyze_risk_case(
    risk_case_id: UUID,
    background_tasks: BackgroundTasks,
    repos: DomainRepositoriesDep,
    analysis_service: AnalysisServiceDep,
) -> dict[str, str]:
    row = await repos.risk_cases.get_or_raise(risk_case_id)
    commitment_id = UUID(row["commitment_id"])
    background_tasks.add_task(analysis_service.analyze_commitment, commitment_id)
    return {"status": "accepted", "risk_case_id": str(risk_case_id)}
