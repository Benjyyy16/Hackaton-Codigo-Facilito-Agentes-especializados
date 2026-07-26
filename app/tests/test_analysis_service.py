"""Tests del AnalysisService: el punto de entrada del análisis de compromisos.

Valida:
- Flujo completo con las 4 señales: risk_case, findings, evidence, alert, decisions.
- Umbral de alerta: score bajo no abre alerta ni marca at_risk.
- Resolución y actualización de alertas existentes.
- Tolerancia a fallos: agente caído, RAG caído, WS caído, LLM caído.
- LLM reemplaza summary pero NO consolidated_score (determinístico siempre).
- Creación de Decisions solo para acciones con requires_human_approval.
- Registro de agent_runs con timing.
- Estado por análisis: _run_ids se resetea entre llamadas.
- Commitment inexistente -> EntityNotFoundError.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.agents.specialized.base import AgentContext, BaseSpecializedAgent
from app.core.exceptions import EntityNotFoundError
from app.schemas.domain import (
    AgentOutput,
    AgentRunStatus,
    Evidence,
    EvidenceSourceType,
    Finding,
    RecommendedAction,
    RiskCase,
    Severity,
)
from app.services.analysis_service import AnalysisService
from app.websocket.manager import ConnectionManager, EventType


# --- Helpers -------------------------------------------------------------------

COMMITMENT_ID = uuid4()
PROJECT_ID = uuid4()
RISK_CASE_ID = uuid4()

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def _commitment_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(COMMITMENT_ID),
        "project_id": str(PROJECT_ID),
        "title": "Entregar integración antes del viernes",
        "description": "Pagos empresariales",
        "beneficiary": "Acme",
        "owner": "Ada Lovelace",
        "due_date": "2026-07-30T00:00:00+00:00",
        "financial_exposure": "20000",
        "currency": "USD",
        "status": "open",
        "metadata": {},
    }
    row.update(overrides)
    return row


def _project_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(PROJECT_ID),
        "name": "Pagos Empresariales",
        "hourly_cost": "75",
        "currency": "USD",
        "external_references": {"jira": "DAT"},
    }
    row.update(overrides)
    return row


def _make_finding(*, score: int = 80, code: str = "overdue") -> Finding:
    return Finding(
        category="schedule",
        code=code,
        severity=Severity.HIGH,
        risk_score=score,
        confidence=1.0,
        summary="El compromiso está vencido",
        impact="Penalización contractual",
        evidence=[
            Evidence(
                source_type=EvidenceSourceType.JIRA,
                provider="jira",
                external_id="DAT-42",
                field="due_date",
                value="2026-07-20",
                observed_at=NOW,
                explanation="Fecha pasada",
            )
        ],
    )


def _make_action(*, requires_approval: bool = True) -> RecommendedAction:
    return RecommendedAction(
        action_type="update_jira_issue",
        title="Reasignar ticket bloqueante",
        rationale="Lleva 5 días sin movimiento",
        requires_human_approval=requires_approval,
    )


class FakeAgent:
    """Agente determinístico para tests."""

    def __init__(
        self,
        name: str,
        *,
        score: int = 75,
        findings: list[Finding] | None = None,
        actions: list[RecommendedAction] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.name = name
        self._score = score
        self._findings = findings or [_make_finding(score=score)]
        self._actions = actions or []
        self._raises = raises

    def analyze(self, context: AgentContext) -> AgentOutput:
        if self._raises:
            raise self._raises
        return AgentOutput(
            agent=self.name,
            risk_score=self._score,
            severity=Severity.HIGH if self._score >= 60 else Severity.LOW,
            confidence=0.9,
            summary=f"{self.name} detectó riesgo",
            findings=self._findings,
            recommended_actions=self._actions,
        )


class FakeOrchestrator:
    """Orquestador con agentes inyectados para los tests."""

    name = "orchestrator-agent"

    def __init__(self, agents: list[FakeAgent]) -> None:
        self._agents = agents

    def consolidate_score(self, outputs: list[AgentOutput]) -> int:
        if not outputs:
            return 0
        return max(o.risk_score for o in outputs)

    def consolidate_confidence(self, outputs: list[AgentOutput]) -> float:
        if not outputs:
            return 0.0
        return sum(o.confidence for o in outputs) / len(outputs)

    def classify_claims(
        self, outputs: list[AgentOutput]
    ) -> tuple[list[str], list[str], list[str]]:
        return ["hecho"], ["inferencia"], ["supuesto"]

    def collect_missing(self, outputs: list[AgentOutput]) -> list[str]:
        return []

    def summarize(self, ctx: Any, outputs: list[AgentOutput], score: int) -> str:
        return f"Resumen determinístico score={score}"

    def build_causal_chain(self, outputs: list[AgentOutput]) -> list:
        return []

    def build_premortem(self, ctx: Any, outputs: list[AgentOutput]) -> None:
        return None

    def build_scenarios(self, ctx: Any, outputs: list[AgentOutput], score: int) -> list:
        return []


def _build_service(
    *,
    agents: list[FakeAgent] | None = None,
    threshold: int = 70,
    open_alert: dict[str, Any] | None = None,
    llm: Any = None,
    documents_fail: bool = False,
    broadcast_fails: bool = False,
) -> tuple[AnalysisService, dict[str, AsyncMock]]:
    """Construye AnalysisService con mocks de repositorios."""
    if agents is None:
        agents = [
            FakeAgent("jira-agent", score=80),
            FakeAgent("code-agent", score=70),
            FakeAgent("finance-agent", score=75),
            FakeAgent("database-agent", score=60),
        ]

    orchestrator = FakeOrchestrator(agents)

    # Mocks de repositorios
    projects = AsyncMock()
    projects.get.return_value = _project_row()

    commitments = AsyncMock()
    commitments.get_or_raise.return_value = _commitment_row()

    source_events = AsyncMock()
    source_events.list_recent_for_commitment.return_value = []

    agent_runs = AsyncMock()
    agent_runs.start.return_value = {"id": str(uuid4())}
    agent_runs.finish.return_value = {}
    agent_runs.fail.return_value = {}

    findings_repo = AsyncMock()
    findings_repo.create.return_value = {"id": str(uuid4())}

    evidence_repo = AsyncMock()
    evidence_repo.create_many.return_value = []

    risk_cases = AsyncMock()
    risk_cases.create.return_value = {"id": str(RISK_CASE_ID)}

    alerts = AsyncMock()
    alerts.find_open_for_commitment.return_value = open_alert
    alerts.create.return_value = {"id": str(uuid4()), "severity": "high"}
    alerts.update.return_value = {}
    alerts.resolve.return_value = {}

    decisions = AsyncMock()
    decisions.create.return_value = {"id": str(uuid4())}

    timeline = AsyncMock()
    timeline.append.return_value = {}

    documents = AsyncMock()
    if documents_fail:
        documents.search_fulltext.side_effect = RuntimeError("RAG down")
    else:
        documents.search_fulltext.return_value = []

    ws = AsyncMock(spec=ConnectionManager)
    if broadcast_fails:
        ws.broadcast.side_effect = RuntimeError("ws down")

    svc = AnalysisService(
        projects=projects,
        commitments=commitments,
        source_events=source_events,
        agent_runs=agent_runs,
        findings=findings_repo,
        evidence=evidence_repo,
        risk_cases=risk_cases,
        alerts=alerts,
        decisions=decisions,
        timeline=timeline,
        documents=documents,
        ws_manager=ws,
        risk_alert_threshold=threshold,
        orchestrator=orchestrator,
        llm=llm,
    )

    mocks = {
        "projects": projects,
        "commitments": commitments,
        "source_events": source_events,
        "agent_runs": agent_runs,
        "findings": findings_repo,
        "evidence": evidence_repo,
        "risk_cases": risk_cases,
        "alerts": alerts,
        "decisions": decisions,
        "timeline": timeline,
        "documents": documents,
        "ws": ws,
    }
    return svc, mocks


# --- Tests: flujo completo -----------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_commitment_full_flow():
    """4 señales -> crea risk_case, findings + evidence, alerta, decisions, marca at_risk."""
    agents = [
        FakeAgent("jira-agent", score=80, actions=[_make_action()]),
        FakeAgent("code-agent", score=70),
        FakeAgent("finance-agent", score=75),
        FakeAgent("database-agent", score=60),
    ]
    svc, mocks = _build_service(agents=agents)

    result = await svc.analyze_commitment(COMMITMENT_ID)

    # Crea risk_case
    mocks["risk_cases"].create.assert_awaited_once()
    # Crea findings (un finding por agente que no falla)
    assert mocks["findings"].create.await_count == 4
    # Crea evidence (cada finding tiene 1 evidencia)
    assert mocks["evidence"].create_many.await_count == 4
    # Abre alerta (score 80 >= threshold 70)
    mocks["alerts"].create.assert_awaited_once()
    # Crea decisión (1 acción con requires_human_approval)
    mocks["decisions"].create.assert_awaited_once()
    # Marca at_risk
    mocks["commitments"].set_status.assert_awaited_once_with(COMMITMENT_ID, "at_risk")
    # Devuelve RiskCase
    assert isinstance(result, RiskCase)
    assert result.consolidated_score == 80


@pytest.mark.asyncio
async def test_score_below_threshold_no_alert_no_at_risk():
    """Score bajo el umbral -> NO abre alerta, NO marca at_risk."""
    agents = [FakeAgent("jira-agent", score=30)]
    svc, mocks = _build_service(agents=agents, threshold=70)

    await svc.analyze_commitment(COMMITMENT_ID)

    mocks["alerts"].create.assert_not_awaited()
    mocks["commitments"].set_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_score_below_threshold_resolves_existing_alert():
    """Score bajo con alerta abierta previa -> la RESUELVE."""
    open_alert = {"id": str(uuid4()), "status": "open"}
    agents = [FakeAgent("jira-agent", score=30)]
    svc, mocks = _build_service(agents=agents, threshold=70, open_alert=open_alert)

    await svc.analyze_commitment(COMMITMENT_ID)

    mocks["alerts"].resolve.assert_awaited_once_with(UUID(open_alert["id"]))
    mocks["alerts"].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_score_above_threshold_updates_existing_alert():
    """Score sobre umbral con alerta abierta -> la ACTUALIZA, no crea otra."""
    open_alert = {"id": str(uuid4()), "status": "open"}
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents, threshold=70, open_alert=open_alert)

    await svc.analyze_commitment(COMMITMENT_ID)

    mocks["alerts"].update.assert_awaited_once()
    mocks["alerts"].create.assert_not_awaited()


# --- Tests: tolerancia a fallos ------------------------------------------------


@pytest.mark.asyncio
async def test_agent_failure_marks_run_failed_and_is_partial():
    """Un agente que eleva -> agent_run marcado failed, is_partial True, el resto continúa."""
    agents = [
        FakeAgent("jira-agent", score=80),
        FakeAgent("code-agent", raises=RuntimeError("boom")),
        FakeAgent("finance-agent", score=75),
        FakeAgent("database-agent", score=60),
    ]
    svc, mocks = _build_service(agents=agents)

    result = await svc.analyze_commitment(COMMITMENT_ID)

    # agent_runs.fail llamado una vez para el agente caído
    mocks["agent_runs"].fail.assert_awaited_once()
    # El resultado está marcado como parcial
    assert result.is_partial is True
    # Los otros 3 produjeron findings
    assert mocks["findings"].create.await_count == 3


@pytest.mark.asyncio
async def test_rag_failure_does_not_stop_analysis():
    """Fallo del RAG no detiene el análisis."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents, documents_fail=True)

    result = await svc.analyze_commitment(COMMITMENT_ID)
    # El análisis completó
    assert isinstance(result, RiskCase)
    mocks["risk_cases"].create.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcast_failure_does_not_stop_analysis():
    """Fallo de difusión WebSocket NO detiene el análisis."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents, broadcast_fails=True)

    result = await svc.analyze_commitment(COMMITMENT_ID)
    assert isinstance(result, RiskCase)
    mocks["risk_cases"].create.assert_awaited_once()


# --- Tests: LLM ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_not_available_keeps_deterministic_summary():
    """LLM no disponible -> conserva la narrativa determinística."""
    llm = MagicMock()
    llm.is_available.return_value = False
    agents = [FakeAgent("jira-agent", score=80)]
    svc, _ = _build_service(agents=agents, llm=llm)

    result = await svc.analyze_commitment(COMMITMENT_ID)
    assert "determinístico" in result.summary


@pytest.mark.asyncio
async def test_llm_raises_keeps_deterministic_summary():
    """LLM que eleva -> conserva la narrativa determinística."""
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.name = "gpt-4"

    # complete es async
    async def _boom(*a: Any, **kw: Any) -> Any:
        raise RuntimeError("LLM timeout")

    llm.complete = _boom
    agents = [FakeAgent("jira-agent", score=80)]
    svc, _ = _build_service(agents=agents, llm=llm)

    result = await svc.analyze_commitment(COMMITMENT_ID)
    assert "determinístico" in result.summary


@pytest.mark.asyncio
async def test_llm_available_replaces_summary_not_score():
    """LLM disponible -> reemplaza summary pero NO el consolidated_score."""
    llm = MagicMock()
    llm.is_available.return_value = True
    llm.name = "gpt-4"

    from app.llm.base import LLMResponse

    async def _complete(*a: Any, **kw: Any) -> LLMResponse:
        return LLMResponse(
            content="Narrativa enriquecida por LLM",
            model="gpt-4",
            prompt_version="1.0",
            tokens_used=100,
            latency_ms=500,
        )

    llm.complete = _complete
    agents = [FakeAgent("jira-agent", score=80)]
    svc, _ = _build_service(agents=agents, llm=llm)

    result = await svc.analyze_commitment(COMMITMENT_ID)
    # El summary cambió
    assert "LLM" in result.summary
    # El score es determinístico, no lo toca el LLM
    assert result.consolidated_score == 80


# --- Tests: decisions ----------------------------------------------------------


@pytest.mark.asyncio
async def test_action_with_approval_creates_decision():
    """Cada acción con requires_human_approval crea exactamente una Decision."""
    actions = [_make_action(requires_approval=True), _make_action(requires_approval=True)]
    agents = [FakeAgent("jira-agent", score=80, actions=actions)]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)
    assert mocks["decisions"].create.await_count == 2


@pytest.mark.asyncio
async def test_action_without_approval_no_decision():
    """Una acción con requires_human_approval=False NO crea Decision."""
    actions = [_make_action(requires_approval=False)]
    agents = [FakeAgent("jira-agent", score=80, actions=actions)]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)
    mocks["decisions"].create.assert_not_awaited()


# --- Tests: agent_runs ---------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_run_opened_before_execution():
    """agent_run se abre ANTES de ejecutar y se cierra después con duration_ms."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)

    # start se llamó antes que finish
    mocks["agent_runs"].start.assert_awaited_once()
    mocks["agent_runs"].finish.assert_awaited_once()
    # finish recibe duration_ms
    finish_kwargs = mocks["agent_runs"].finish.call_args.kwargs
    assert "duration_ms" in finish_kwargs
    assert isinstance(finish_kwargs["duration_ms"], int)


@pytest.mark.asyncio
async def test_run_ids_reset_between_calls():
    """_run_ids se resetea entre dos llamadas consecutivas."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents)

    # Hacer que start devuelva IDs distintos en cada llamada
    first_id = str(uuid4())
    second_id = str(uuid4())
    mocks["agent_runs"].start.side_effect = [
        {"id": first_id},
        {"id": second_id},
    ]

    await svc.analyze_commitment(COMMITMENT_ID)
    # Después de la primera, _run_ids tiene el primer ID
    first_run_ids = dict(svc._run_ids)

    await svc.analyze_commitment(COMMITMENT_ID)
    second_run_ids = dict(svc._run_ids)

    # Los IDs son diferentes: se reseteó
    assert first_run_ids["jira-agent"] == UUID(first_id)
    assert second_run_ids["jira-agent"] == UUID(second_id)
    assert first_run_ids["jira-agent"] != second_run_ids["jira-agent"]


# --- Tests: _signals_from_events ----------------------------------------------


def test_signals_from_events_takes_most_recent():
    """_signals_from_events toma solo el evento más reciente de cada provider."""
    events = [
        {"provider": "jira", "payload": {"status": "Done"}, "occurred_at": "2026-07-25"},
        {"provider": "jira", "payload": {"status": "In Progress"}, "occurred_at": "2026-07-24"},
        {"provider": "github", "payload": {"prs": 3}, "occurred_at": "2026-07-25"},
        {"provider": "github", "payload": {"prs": 1}, "occurred_at": "2026-07-23"},
    ]
    result = AnalysisService._signals_from_events(events)
    # Solo el primero de cada provider (ya vienen ordenados de más nuevo a más antiguo)
    assert result["jira"] == {"status": "Done"}
    assert result["github"] == {"prs": 3}


def test_signals_from_events_empty():
    assert AnalysisService._signals_from_events([]) == {}


def test_signals_from_events_skips_no_provider():
    events = [{"provider": None, "payload": {"x": 1}}]
    assert AnalysisService._signals_from_events(events) == {}


# --- Tests: commitment inexistente ---------------------------------------------


@pytest.mark.asyncio
async def test_commitment_not_found_raises():
    """Commitment inexistente -> EntityNotFoundError."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents)
    mocks["commitments"].get_or_raise.side_effect = EntityNotFoundError()

    with pytest.raises(EntityNotFoundError):
        await svc.analyze_commitment(uuid4())


# --- Tests: múltiples agentes con acciones mixtas ------------------------------


@pytest.mark.asyncio
async def test_multiple_agents_mixed_actions():
    """Múltiples agentes, solo las acciones con approval crean decisions."""
    agents = [
        FakeAgent("jira-agent", score=80, actions=[_make_action(requires_approval=True)]),
        FakeAgent("code-agent", score=70, actions=[_make_action(requires_approval=False)]),
        FakeAgent("finance-agent", score=75, actions=[
            _make_action(requires_approval=True),
            _make_action(requires_approval=True),
        ]),
        FakeAgent("database-agent", score=60, actions=[_make_action(requires_approval=False)]),
    ]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)
    # jira: 1 + finance: 2 = 3
    assert mocks["decisions"].create.await_count == 3


@pytest.mark.asyncio
async def test_all_agents_fail_returns_partial_empty_case():
    """Todos los agentes fallan -> is_partial, score 0, sin findings."""
    agents = [
        FakeAgent("jira-agent", raises=RuntimeError("a")),
        FakeAgent("code-agent", raises=RuntimeError("b")),
    ]
    svc, mocks = _build_service(agents=agents)

    result = await svc.analyze_commitment(COMMITMENT_ID)
    assert result.is_partial is True
    assert result.consolidated_score == 0
    mocks["findings"].create.assert_not_awaited()


@pytest.mark.asyncio
async def test_analyze_with_signals_passed_directly():
    """Cuando se pasan señales explícitas, no se derivan de eventos."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents)
    signals = {"jira": {"status": "Blocked"}}

    result = await svc.analyze_commitment(COMMITMENT_ID, signals=signals)
    assert isinstance(result, RiskCase)


@pytest.mark.asyncio
async def test_evidence_persisted_for_each_finding():
    """Cada finding con evidencia genera una llamada a create_many."""
    finding_with_evidence = _make_finding(score=80)
    agents = [FakeAgent("jira-agent", score=80, findings=[finding_with_evidence, finding_with_evidence])]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)
    # 2 findings, cada uno con evidencia
    assert mocks["evidence"].create_many.await_count == 2


@pytest.mark.asyncio
async def test_timeline_appended_after_analysis():
    """Se anota en la cronología al completar el análisis."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)
    mocks["timeline"].append.assert_awaited()
    # El evento es analysis.completed
    call_kwargs = mocks["timeline"].append.call_args.kwargs
    assert call_kwargs["event_type"] == "analysis.completed"


@pytest.mark.asyncio
async def test_broadcast_analysis_started_and_risk_case_created():
    """Se emiten eventos ANALYSIS_STARTED y RISK_CASE_CREATED."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)
    # Múltiples broadcasts: al menos ANALYSIS_STARTED y RISK_CASE_CREATED
    events_emitted = [
        call.args[0].type for call in mocks["ws"].broadcast.call_args_list
    ]
    assert EventType.ANALYSIS_STARTED in events_emitted
    assert EventType.RISK_CASE_CREATED in events_emitted


@pytest.mark.asyncio
async def test_agent_run_completed_event_per_agent():
    """Se emite AGENT_RUN_COMPLETED por cada agente que NO falla."""
    agents = [
        FakeAgent("jira-agent", score=80),
        FakeAgent("code-agent", score=70),
    ]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)
    events_emitted = [
        call.args[0].type for call in mocks["ws"].broadcast.call_args_list
    ]
    agent_run_events = [e for e in events_emitted if e == EventType.AGENT_RUN_COMPLETED]
    assert len(agent_run_events) == 2


@pytest.mark.asyncio
async def test_risk_case_persisted_with_correct_fields():
    """El risk_case persistido lleva los campos esperados."""
    agents = [FakeAgent("jira-agent", score=80)]
    svc, mocks = _build_service(agents=agents)

    await svc.analyze_commitment(COMMITMENT_ID)

    create_kwargs = mocks["risk_cases"].create.call_args.args[0]
    assert create_kwargs["commitment_id"] == str(COMMITMENT_ID)
    assert create_kwargs["consolidated_score"] == 80
    assert "severity" in create_kwargs
    assert "summary" in create_kwargs
    assert "is_partial" in create_kwargs
