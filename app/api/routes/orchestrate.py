"""Análisis sin persistencia: el pipeline completo sobre señales dadas.

Ejecuta los cuatro agentes especializados y el orquestador nuevo, y devuelve el
``RiskCase`` completo —cadena causal, pre-mortem, tres escenarios, hechos frente a
inferencias, y las acciones que requerirían aprobación— **sin escribir nada**.

Existe por una razón concreta: el flujo persistente (``POST /commitments/{id}/analyze``)
necesita que el esquema de ``db/schema.sql`` esté aplicado en Supabase. Hasta que lo
esté, ese flujo devuelve 503 y no hay forma de ver el análisis. Este endpoint permite
ejercitar y mostrar toda la lógica de riesgo sin base de datos.

Lo que NO hace, y conviene tener claro al leer su respuesta:

* no crea ``agent_runs``, así que no hay rastro de auditoría;
* no persiste hallazgos ni evidencia;
* no abre alerta ni crea ``Decision``, así que no hay nada que aprobar de verdad:
  las acciones vienen marcadas como propuestas;
* no difunde por WebSocket.

Es una vista previa del análisis, no el análisis registrado. La diferencia importa y por
eso la respuesta la declara en ``persisted: false``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.agents.risk_orchestrator import RiskOrchestrator
from app.agents.specialized import AgentContext
from app.core.logging import get_logger
from app.schemas.domain import (
    AgentOutput,
    CommitmentSnapshot,
    Priority,
    ProjectSnapshot,
    RetrievedChunk,
    RiskCase,
)

logger = get_logger("api.orchestrate")

router = APIRouter(prefix="/agents", tags=["agents"])

#: Fixture del caso demo. Se lee del mismo fichero que usa el seed de Supabase para que
#: la vista previa y el flujo persistente no puedan divergir.
DEMO_CASE_PATH = Path(__file__).resolve().parents[3] / "db" / "seed" / "demo_case.json"


class CommitmentInput(BaseModel):
    """Compromiso a analizar, tal como lo envía el cliente."""

    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    beneficiary: str | None = None
    owner: str | None = None
    due_date: datetime | None = None
    financial_exposure: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    priority: Priority = Priority.MEDIUM


class ProjectInput(BaseModel):
    name: str = Field(default="Proyecto", min_length=1, max_length=200)
    hourly_cost: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class OrchestrateRequest(BaseModel):
    """Cuerpo de ``POST /agents/orchestrate``."""

    commitment: CommitmentInput
    project: ProjectInput = Field(default_factory=ProjectInput)
    #: Señales por proveedor: ``jira``, ``github``, ``supabase``, ``finance``.
    #: Un proveedor ausente no es un error: el agente correspondiente lo declara en
    #: ``missing_information`` y queda como ``skipped``.
    signals: dict[str, Any] = Field(default_factory=dict)
    documents: list[dict[str, Any]] = Field(default_factory=list)


class ProposedAction(BaseModel):
    """Acción que el sistema propondría. No es una ``Decision``: nada se ha creado."""

    model_config = ConfigDict(frozen=True)

    agent: str
    action_type: str
    title: str
    rationale: str
    requires_human_approval: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)


class OrchestrateResponse(BaseModel):
    """Vista previa del análisis, sin persistencia."""

    #: Siempre ``False`` en este endpoint. Está explícito para que un cliente no
    #: confunda esta respuesta con un análisis registrado.
    persisted: bool = False
    risk_case: RiskCase
    agent_outputs: list[AgentOutput]
    proposed_actions: list[ProposedAction]
    analyzed_at: datetime


def _build_context(request: OrchestrateRequest) -> AgentContext:
    return AgentContext(
        commitment=CommitmentSnapshot(
            title=request.commitment.title,
            description=request.commitment.description,
            beneficiary=request.commitment.beneficiary,
            owner=request.commitment.owner,
            due_date=request.commitment.due_date,
            financial_exposure=request.commitment.financial_exposure,
            currency=request.commitment.currency,
            priority=request.commitment.priority,
        ),
        project=ProjectSnapshot(
            name=request.project.name,
            hourly_cost=request.project.hourly_cost,
            currency=request.project.currency,
        ),
        now=datetime.now(UTC),
        signals=request.signals,
        documents=[
            RetrievedChunk(
                title=str(doc.get("title", "")),
                content=str(doc.get("content", "")),
                score=1.0,
                strategy="fulltext",
            )
            for doc in request.documents
        ],
    )


def _proposed_actions(outputs: list[AgentOutput]) -> list[ProposedAction]:
    return [
        ProposedAction(
            agent=output.agent,
            action_type=action.action_type,
            title=action.title,
            rationale=action.rationale,
            requires_human_approval=action.requires_human_approval,
            payload=action.payload,
        )
        for output in outputs
        for action in output.recommended_actions
    ]


@router.post(
    "/orchestrate",
    response_model=OrchestrateResponse,
    summary="Análisis completo sin persistencia",
    description=(
        "Ejecuta los cuatro agentes especializados y el orquestador sobre las señales "
        "enviadas, y devuelve el caso de riesgo completo: puntuación consolidada, cadena "
        "causal, pre-mortem, tres escenarios de recuperación, separación entre hechos, "
        "inferencias y supuestos, y las acciones que requerirían aprobación.\n\n"
        "**No escribe nada.** No hay `agent_runs`, ni alerta, ni `Decision` real. La "
        "respuesta lo declara en `persisted: false`.\n\n"
        "Para el flujo registrado y auditable usar `POST /commitments/{id}/analyze`, que "
        "requiere el esquema de `db/schema.sql` aplicado en Supabase.\n\n"
        "Un proveedor ausente en `signals` no es un error: su agente queda `skipped` y "
        "declara el hueco en `missing_information`."
    ),
)
async def orchestrate(request: OrchestrateRequest) -> OrchestrateResponse:
    """Ejecuta el pipeline y devuelve el análisis."""
    context = _build_context(request)
    risk_case = RiskOrchestrator().analyze(context)

    return OrchestrateResponse(
        persisted=False,
        risk_case=risk_case,
        agent_outputs=risk_case.agent_outputs,
        proposed_actions=_proposed_actions(risk_case.agent_outputs),
        analyzed_at=context.now,
    )


@router.post(
    "/orchestrate/demo",
    response_model=OrchestrateResponse,
    summary="Análisis del caso demo, sin persistencia",
    description=(
        "Ejecuta el pipeline sobre el caso de demostración: *Entregar integración de pagos "
        "empresariales antes del viernes*, con penalización contractual, issue bloqueado sin "
        "responsable, pull request con checks fallidos, migración sin rollback y tabla sin "
        "RLS.\n\n"
        "El fixture es el mismo que alimenta el seed de Supabase (`db/seed/demo_case.json`), "
        "así que la vista previa y el flujo persistente no pueden divergir.\n\n"
        "El resultado es reproducible: riesgo crítico con los cuatro agentes contribuyendo."
    ),
)
async def orchestrate_demo() -> OrchestrateResponse:
    """Ejecuta el pipeline sobre el fixture del caso demo.

    Las fechas del fixture se reajustan al momento de la llamada para que el compromiso
    siga apareciendo vencido. Sin esto, el caso perdería su señal más importante conforme
    pasara el tiempo y el resultado dejaría de ser reproducible.
    """
    demo = json.loads(DEMO_CASE_PATH.read_text(encoding="utf-8"))
    commitment = demo["commitment"]
    project = demo.get("project", {})

    request = OrchestrateRequest(
        commitment=CommitmentInput(
            title=commitment["title"],
            description=commitment.get("description"),
            beneficiary=commitment.get("beneficiary"),
            owner=commitment.get("owner"),
            due_date=_relative_due_date(commitment.get("due_date")),
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

    return await orchestrate(request)


def _relative_due_date(raw: Any) -> datetime | None:
    """Devuelve una fecha vencida hace un día, conservando la intención del fixture.

    El fixture declara una fecha pasada. Usarla literalmente funciona hoy y sigue
    funcionando en un año, pero el número de días de retraso crecería sin control y el
    caso dejaría de ser el mismo. Anclarla a "ayer" mantiene el escenario estable.
    """
    if raw is None:
        return None
    from datetime import timedelta

    return datetime.now(UTC) - timedelta(days=1)
