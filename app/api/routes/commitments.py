"""Rutas de compromisos."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, status

from app.api.deps import AnalysisServiceDep, DomainRepositoriesDep
from app.schemas.domain import (
    CommitmentCreate,
    CommitmentRead,
    CommitmentUpdate,
    TimelineEventRead,
)

router = APIRouter(prefix="/commitments", tags=["commitments"])


@router.get(
    "",
    response_model=list[CommitmentRead],
    summary="Listar compromisos",
    description="Lista paginada con filtro opcional por project_id y status.",
)
async def list_commitments(
    repos: DomainRepositoriesDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    project_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[CommitmentRead]:
    filters: dict[str, str] = {}
    if project_id:
        filters["project_id"] = str(project_id)
    if status_filter:
        filters["status"] = status_filter
    page = await repos.commitments.list_page(limit=limit, offset=offset, filters=filters)
    return [CommitmentRead.model_validate(row) for row in page.items]


@router.post(
    "",
    response_model=CommitmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear compromiso",
    description="Crea un nuevo compromiso vinculado a un proyecto.",
)
async def create_commitment(
    body: CommitmentCreate,
    repos: DomainRepositoriesDep,
) -> CommitmentRead:
    row = await repos.commitments.create(body.model_dump(mode="json"))
    return CommitmentRead.model_validate(row)


@router.get(
    "/{commitment_id}",
    response_model=CommitmentRead,
    summary="Obtener compromiso",
    description="Devuelve un compromiso por ID. 404 si no existe.",
)
async def get_commitment(
    commitment_id: UUID,
    repos: DomainRepositoriesDep,
) -> CommitmentRead:
    row = await repos.commitments.get_or_raise(commitment_id)
    return CommitmentRead.model_validate(row)


@router.patch(
    "/{commitment_id}",
    response_model=CommitmentRead,
    summary="Actualizar compromiso",
    description="Actualización parcial de un compromiso existente.",
)
async def update_commitment(
    commitment_id: UUID,
    body: CommitmentUpdate,
    repos: DomainRepositoriesDep,
) -> CommitmentRead:
    # Solo enviar campos que el cliente proporcionó
    payload = body.model_dump(mode="json", exclude_unset=True)
    row = await repos.commitments.update(commitment_id, payload)
    return CommitmentRead.model_validate(row)


@router.post(
    "/{commitment_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Disparar análisis",
    description="Lanza el análisis de riesgo en segundo plano y responde 202 inmediatamente.",
)
async def analyze_commitment(
    commitment_id: UUID,
    background_tasks: BackgroundTasks,
    analysis_service: AnalysisServiceDep,
    repos: DomainRepositoriesDep,
) -> dict[str, str]:
    # Validar que existe antes de encolar
    await repos.commitments.get_or_raise(commitment_id)
    background_tasks.add_task(analysis_service.analyze_commitment, commitment_id)
    return {"status": "accepted", "commitment_id": str(commitment_id)}


@router.get(
    "/{commitment_id}/findings",
    summary="Hallazgos del compromiso",
    description="Devuelve los hallazgos producidos por los agentes para este compromiso.",
)
async def get_commitment_findings(
    commitment_id: UUID,
    repos: DomainRepositoriesDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict]:
    # Validar existencia
    await repos.commitments.get_or_raise(commitment_id)
    return await repos.findings.list_for_commitment(commitment_id, limit=limit)


@router.get(
    "/{commitment_id}/timeline",
    response_model=list[TimelineEventRead],
    summary="Cronología del compromiso",
    description="Devuelve la historia legible del compromiso.",
)
async def get_commitment_timeline(
    commitment_id: UUID,
    repos: DomainRepositoriesDep,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[TimelineEventRead]:
    await repos.commitments.get_or_raise(commitment_id)
    rows = await repos.timeline.list_for_commitment(commitment_id, limit=limit)
    return [TimelineEventRead.model_validate(row) for row in rows]
