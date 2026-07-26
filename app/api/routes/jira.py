"""Sincronización manual con Jira."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import JiraSyncServiceDep, PrincipalDep
from app.core.exceptions import ErrorResponse
from app.schemas.jira import JiraSyncRequest, JiraSyncResult

router = APIRouter(tags=["jira"])


@router.post(
    "/jira/sync",
    response_model=JiraSyncResult,
    status_code=status.HTTP_200_OK,
    summary="Sincroniza un proyecto de Jira mediante JQL",
    description=(
        "Carga el estado actual de un proyecto para tener una base sobre la que detectar "
        "cambios. Los cambios posteriores llegan por webhook, no por sondeo.\n\n"
        "Si no se indica JQL, se construye a partir de la clave de proyecto. La operación es "
        "idempotente: repetirla sin cambios en Jira no crea eventos nuevos."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "El proyecto no existe en Jira.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": "Jira no está disponible o rechazó las credenciales.",
        },
    },
)
async def sync_jira_project(
    request: JiraSyncRequest,
    service: JiraSyncServiceDep,
    _principal: PrincipalDep,
) -> JiraSyncResult:
    """Ejecuta la sincronización inicial de un proyecto (RF-4)."""
    return await service.sync_project(
        request.project_key, jql=request.jql, max_issues=request.max_issues
    )
