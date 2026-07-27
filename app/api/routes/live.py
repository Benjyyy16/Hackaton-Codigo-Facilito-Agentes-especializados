"""Rutas del análisis en vivo de Datgent.

Expone el ciclo completo: arrancar análisis, consultar estado, aprobar/rechazar
decisiones, ver provenance de datos y simular eventos para demo.

Toda la progresión ocurre en el backend. El frontend solo suscribe WebSocket y
consulta estado; no simula nada en React.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import ProviderRegistryDep, SettingsDep, WsManagerDep
from app.api.routes.orchestrate import (
    DEMO_CASE_PATH,
    CommitmentInput,
    OrchestrateRequest,
    ProjectInput,
    _build_context,
)
from app.core.config import Environment, Settings
from app.core.logging import get_logger
from app.providers.registry import ProviderRegistry
from app.schemas.domain import Priority
from app.schemas.events import ProviderName
from app.services.live_analysis_service import (
    CerebroState,
    DomainError,
    LiveAnalysisService,
)
from app.websocket.manager import ConnectionManager, EventType, WsEvent

logger = get_logger("api.live")

router = APIRouter(prefix="/live", tags=["live"])

# --- Singleton del servicio (creado al primer uso por request) ---
# Se almacena en app.state para compartir entre requests.


def _get_service(request: Request) -> LiveAnalysisService:
    """Obtiene o crea el LiveAnalysisService desde app.state."""
    svc = getattr(request.app.state, "live_analysis_service", None)
    if svc is None:
        ws_manager: ConnectionManager = getattr(
            request.app.state, "ws_manager", ConnectionManager()
        )
        svc = LiveAnalysisService(ws_manager)
        request.app.state.live_analysis_service = svc
    return svc


def _check_demo_access(settings: Settings) -> None:
    """404 si no es demo/dev/test."""
    allowed = (
        settings.DEMO_MODE_ENABLED
        or settings.ENV in (Environment.DEVELOPMENT, Environment.TEST)
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def _provenance_for_registry(registry: ProviderRegistry) -> dict[str, str]:
    """Mapea providers a 'real' o 'demo' según estén registrados."""
    registered = {name.value for name in registry.names()}
    result: dict[str, str] = {}
    for pn in ProviderName:
        result[pn.value] = "real" if pn.value in registered else "demo"
    return result


# --- Modelos de request/response ---


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1, max_length=200)


class RejectBody(BaseModel):
    rejected_by: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)


# --- Endpoints ---


@router.post(
    "/analysis",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Inicia un análisis en vivo",
)
async def start_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    registry: ProviderRegistryDep,
    ws_manager: WsManagerDep,
    body: OrchestrateRequest | None = None,
) -> dict[str, Any]:
    """Arranca el análisis. Body opcional: si vacío usa caso demo. 409 si ya hay activo."""
    svc = _get_service(request)

    if svc.has_active_session():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya hay una sesión de análisis activa.",
        )

    # Si no viene body, usar caso demo
    if body is None:
        demo = json.loads(DEMO_CASE_PATH.read_text(encoding="utf-8"))
        commitment = demo["commitment"]
        project = demo.get("project", {})
        body = OrchestrateRequest(
            commitment=CommitmentInput(
                title=commitment["title"],
                description=commitment.get("description"),
                beneficiary=commitment.get("beneficiary"),
                owner=commitment.get("owner"),
                due_date=datetime.now(UTC) - timedelta(days=1),
                financial_exposure=Decimal(str(commitment.get("financial_exposure", 0))),
                currency=commitment.get("currency", "USD"),
                priority=Priority(commitment.get("priority", "medium")),
            ),
            project=ProjectInput(
                name=project.get("name", "Datgent"),
                hourly_cost=Decimal(str(project.get("hourly_cost", 0))),
                currency=project.get("currency", "USD"),
            ),
            signals=demo.get("signals", {}),
            documents=demo.get("documents", []),
        )

    context = _build_context(body)
    session_id = uuid4()
    provenance = _provenance_for_registry(registry)

    background_tasks.add_task(svc.run, session_id, context, provenance=provenance)

    return {
        "session_id": str(session_id),
        "state": CerebroState.READY.value,
    }


@router.get(
    "/analysis/{session_id}",
    summary="Estado completo de una sesión de análisis",
)
async def get_analysis(request: Request, session_id: UUID) -> dict[str, Any]:
    svc = _get_service(request)
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada")
    return session.to_dict()


@router.get(
    "/analysis/{session_id}/timeline",
    summary="Timeline de una sesión",
)
async def get_timeline(request: Request, session_id: UUID) -> list[dict[str, Any]]:
    svc = _get_service(request)
    session = svc.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesión no encontrada")
    return [t.to_dict() for t in session.timeline]


@router.post(
    "/decisions/{decision_id}/approve",
    summary="Aprobar una decisión pendiente",
)
async def approve_decision(
    request: Request,
    decision_id: UUID,
    body: ApproveBody,
) -> dict[str, Any]:
    svc = _get_service(request)
    try:
        decision = await svc.approve_decision(decision_id, body.approved_by)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decisión no encontrada")
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return {
        "decision_id": str(decision.id),
        "approved_by": decision.approved_by,
        "approved_at": decision.approved_at.isoformat() if decision.approved_at else None,
        "execution_status": decision.execution_status.value,
    }


@router.post(
    "/decisions/{decision_id}/reject",
    summary="Rechazar una decisión pendiente",
)
async def reject_decision(
    request: Request,
    decision_id: UUID,
    body: RejectBody,
) -> dict[str, Any]:
    svc = _get_service(request)
    try:
        decision = await svc.reject_decision(decision_id, body.rejected_by, body.reason)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decisión no encontrada")
    except DomainError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return {
        "decision_id": str(decision.id),
        "rejected_by": decision.approved_by,
        "reason": decision.rejection_reason,
    }


@router.get(
    "/provenance",
    summary="Provenance de datos: qué providers son reales y cuáles demo",
)
async def get_provenance(
    request: Request,
    registry: ProviderRegistryDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    """Indica qué providers están conectados (datos reales) y cuáles son demo."""
    registered = {name.value for name in registry.names()}
    svc = _get_service(request)

    # Mapeo provider -> label legible
    labels: dict[str, str] = {
        "jira": "JIRA",
        "github": "GITHUB",
        "notion": "NOTION",
        "slack": "SLACK",
        "vercel": "VERCEL",
        "aws": "AWS",
        "rightway": "FINANZAS",
    }

    providers = []
    for pn in ProviderName:
        connected = pn.value in registered
        prov = "real" if connected else "demo"
        label_base = labels.get(pn.value, pn.value.upper())
        if connected:
            label = f"{label_base} CONECTADO · DATOS REALES"
        else:
            label = f"{label_base} · DATOS DEMO"
        providers.append({
            "provider": pn.value,
            "connected": connected,
            "provenance": prov,
            "label": label,
        })

    # ¿Hay alguna sesión activa y es demo?
    demo_session = any(
        not s.is_active or s.is_active
        for s in svc.sessions.values()
    ) and not all(
        pn.value in registered for pn in ProviderName
    )

    return {
        "providers": providers,
        "demo_session": demo_session,
    }


@router.post(
    "/simulate/jira",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Simula un evento Jira crítico y re-ejecuta análisis (solo demo)",
)
async def simulate_jira(
    request: Request,
    background_tasks: BackgroundTasks,
    registry: ProviderRegistryDep,
    settings: SettingsDep,
    ws_manager: WsManagerDep,
) -> dict[str, Any]:
    """Inyecta un issue Jira crítico y re-ejecuta el análisis."""
    _check_demo_access(settings)

    svc = _get_service(request)

    # Emitir source_event.received
    await svc._safe_broadcast(WsEvent(
        type=EventType.SOURCE_EVENT_RECEIVED,
        data={
            "provider": "jira",
            "event_type": "issue.critical_blocked",
            "summary": "Issue crítico bloqueado sin responsable con fecha vencida",
        },
    ))

    # Construir contexto con señales Jira aumentadas
    demo = json.loads(DEMO_CASE_PATH.read_text(encoding="utf-8"))
    commitment = demo["commitment"]
    project = demo.get("project", {})
    signals = demo.get("signals", {})

    # Inyectar señal Jira crítica extra
    jira_signals = signals.get("jira", {})
    jira_signals["status"] = "blocked"
    jira_signals["assignee"] = None
    jira_signals["priority"] = "critical"
    jira_signals["due_date"] = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    jira_signals["external_dependency"] = "Payment Gateway v3 API — proveedor no responde"
    jira_signals["blocked_reason"] = "Dependencia externa sin respuesta desde hace 5 días"
    signals["jira"] = jira_signals

    body = OrchestrateRequest(
        commitment=CommitmentInput(
            title=commitment["title"],
            description=commitment.get("description"),
            beneficiary=commitment.get("beneficiary"),
            owner=commitment.get("owner"),
            due_date=datetime.now(UTC) - timedelta(days=3),
            financial_exposure=Decimal(str(commitment.get("financial_exposure", 0))) * 2,
            currency=commitment.get("currency", "USD"),
            priority=Priority.CRITICAL,
        ),
        project=ProjectInput(
            name=project.get("name", "Datgent"),
            hourly_cost=Decimal(str(project.get("hourly_cost", 0))),
            currency=project.get("currency", "USD"),
        ),
        signals=signals,
        documents=demo.get("documents", []),
    )

    context = _build_context(body)
    session_id = uuid4()
    provenance = _provenance_for_registry(registry)

    # Limpiar sesión anterior si existe
    # (simulate siempre crea nueva sesión)
    background_tasks.add_task(svc.run, session_id, context, provenance=provenance)

    return {
        "session_id": str(session_id),
        "state": CerebroState.READY.value,
        "message": "Evento Jira crítico inyectado, análisis re-ejecutado.",
    }


@router.delete(
    "/reset",
    summary="Limpia sesiones en memoria (solo demo)",
)
async def reset_sessions(
    request: Request,
    settings: SettingsDep,
) -> dict[str, str]:
    _check_demo_access(settings)
    svc = _get_service(request)
    svc.reset()
    return {"status": "cleared"}
