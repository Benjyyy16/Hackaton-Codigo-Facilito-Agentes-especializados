"""Rutas de proyectos."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import DomainRepositoriesDep
from app.schemas.domain import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get(
    "",
    response_model=list[ProjectRead],
    summary="Listar proyectos",
    description="Devuelve una lista paginada de proyectos.",
)
async def list_projects(
    repos: DomainRepositoriesDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectRead]:
    page = await repos.projects.list_page(limit=limit, offset=offset)
    return [ProjectRead.model_validate(row) for row in page.items]


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proyecto",
    description="Crea un nuevo proyecto y lo devuelve.",
)
async def create_project(
    body: ProjectCreate,
    repos: DomainRepositoriesDep,
) -> ProjectRead:
    row = await repos.projects.create(body.model_dump(mode="json"))
    return ProjectRead.model_validate(row)


@router.get(
    "/{project_id}",
    response_model=ProjectRead,
    summary="Obtener proyecto",
    description="Devuelve un proyecto por su ID. 404 si no existe.",
)
async def get_project(
    project_id: UUID,
    repos: DomainRepositoriesDep,
) -> ProjectRead:
    row = await repos.projects.get_or_raise(project_id)
    return ProjectRead.model_validate(row)
