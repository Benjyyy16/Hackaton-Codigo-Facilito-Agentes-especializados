"""Ruta para ejecutar análisis de agentes desde el frontend."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.agents.base import AgentContext
from app.agents.orchestrator import OrchestratorAgent
from app.api.deps import get_settings_dep
from app.core.config import Settings
from app.schemas.analysis import AnalysisResult, CommitmentSnapshot, ProjectSnapshot
from app.schemas.events import ExternalEvent, EventKind, ProviderName
from app.services.auth_service import AuthService, AuthenticationError

router = APIRouter(prefix="/agents", tags=["agents"])
security = HTTPBearer()


class AnalysisRequest(BaseModel):
    """Request para ejecutar análisis de riesgo."""

    project_key: str = Field(default="DEMO", description="Clave del proyecto")
    issue_key: str = Field(default="DEMO-1", description="Clave del issue")
    title: str = Field(default="Tarea de ejemplo", description="Título del compromiso")
    due_date: str | None = Field(default=None, description="Fecha de vencimiento ISO")
    estimated_hours: float | None = Field(default=None, description="Horas estimadas")
    hourly_cost: float = Field(default=50.0, description="Costo por hora del equipo")


class AgentInfo(BaseModel):
    """Info de un agente disponible."""

    name: str
    description: str
    capabilities: list[str]


@router.get(
    "",
    summary="Listar agentes disponibles",
    description="Devuelve la lista de agentes especializados del sistema.",
)
async def list_agents() -> list[AgentInfo]:
    return [
        AgentInfo(
            name="commitment",
            description="Analiza compromisos y fechas de vencimiento",
            capabilities=["vencimiento", "estado", "reapertura", "sin_fecha"],
        ),
        AgentInfo(
            name="technical",
            description="Detecta señales técnicas de riesgo",
            capabilities=["bloqueo", "estancamiento", "sin_asignar", "reasignaciones"],
        ),
        AgentInfo(
            name="financial",
            description="Calcula impacto económico del riesgo",
            capabilities=["impacto_horas", "costo_estimado", "presupuesto"],
        ),
        AgentInfo(
            name="risk",
            description="Compone el riesgo global ponderado",
            capabilities=["score_global", "severidad", "señal_dominante"],
        ),
        AgentInfo(
            name="orchestrator",
            description="Orquesta todos los agentes y tolera fallos parciales",
            capabilities=["ejecucion_paralela", "tolerancia_fallos", "composicion"],
        ),
    ]


@router.post(
    "/analyze",
    summary="Ejecutar análisis de riesgo",
    description="Ejecuta el pipeline de agentes sobre un contexto dado y devuelve el resultado.",
    response_model=AnalysisResult,
)
async def run_analysis(
    request: AnalysisRequest,
    settings: Annotated[Settings, Depends(get_settings_dep)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))] = None,
) -> AnalysisResult:
    # Verificar JWT si viene token (opcional para demo)
    if credentials:
        try:
            auth_service = AuthService(settings)
            auth_service.get_current_user(credentials.credentials)
        except AuthenticationError:
            pass  # Permitir sin auth para demo

    # Construir contexto para los agentes
    now = datetime.now(timezone.utc)

    due_date = None
    if request.due_date:
        try:
            due_date = datetime.fromisoformat(request.due_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    event = ExternalEvent(
        provider=ProviderName.JIRA,
        workspace_key=request.project_key,
        external_id=request.issue_key,
        external_key=request.issue_key,
        kind=EventKind.WORK_ITEM_UPDATED,
        occurred_at=now,
        title=request.title,
        state="In Progress",
        owner="user",
        due_date=due_date,
        estimated_hours=request.estimated_hours,
        raw_payload={
            "key": request.issue_key,
            "summary": request.title,
            "status": "In Progress",
            "source": "datgent-frontend",
        },
    )

    commitment = CommitmentSnapshot(
        jira_issue_key=request.issue_key,
        title=request.title,
        due_date=due_date,
        estimated_hours=request.estimated_hours,
    )

    project = ProjectSnapshot(
        jira_project_key=request.project_key,
        hourly_cost=request.hourly_cost,
    )

    context = AgentContext(
        event=event,
        now=now,
        commitment=commitment,
        project=project,
    )

    # Ejecutar orquestador
    orchestrator = OrchestratorAgent()
    result = orchestrator.analyse(context)

    return result
