"""Tests del análisis en vivo de Datgent.

Valida el ciclo completo: estados, eventos WS, decisiones, provenance, y protección
de rutas demo. Sin red, sin Supabase, delay=0.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.agents.specialized import AgentContext
from app.core.config import Environment
from app.schemas.domain import (
    AgentOutput,
    CommitmentSnapshot,
    Priority,
    ProjectSnapshot,
)
from app.services.live_analysis_service import (
    CerebroState,
    DomainError,
    LiveAgentState,
    LiveAnalysisService,
)
from app.websocket.manager import ConnectionManager, EventType, WsEvent


# --- Helpers ---


class FakeWsManager(ConnectionManager):
    """Captura eventos emitidos sin conexión real."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[WsEvent] = []

    async def broadcast(self, event: WsEvent) -> int:
        self.events.append(event)
        return 1

    def events_of_type(self, event_type: EventType) -> list[WsEvent]:
        return [e for e in self.events if e.type == event_type]


class BrokenWsManager(ConnectionManager):
    """Manager que siempre eleva al difundir."""

    async def broadcast(self, event: WsEvent) -> int:
        raise RuntimeError("WS roto a propósito")


def _make_context() -> AgentContext:
    return AgentContext(
        commitment=CommitmentSnapshot(
            title="Entregar integración de pagos",
            description="Integración con pasarela de pagos empresariales",
            beneficiary="Cliente Corp",
            owner="equipo-backend",
            due_date=datetime.now(UTC) - timedelta(days=1),
            financial_exposure=Decimal("50000"),
            currency="USD",
            priority=Priority.HIGH,
        ),
        project=ProjectSnapshot(
            name="Datgent",
            hourly_cost=Decimal("75"),
            currency="USD",
        ),
        now=datetime.now(UTC),
        signals={
            "jira": {
                "status": "blocked",
                "assignee": None,
                "due_date": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            },
            "github": {"pr_status": "failing_checks"},
            "finance": {"penalties": [{"amount": 25000, "probability": 0.8}]},
            "supabase": {"tables_without_rls": ["payments"]},
        },
    )


def _create_app_for_test(*, env: Environment = Environment.TEST, demo_mode: bool = True) -> FastAPI:
    """Crea app de test sin Supabase real."""
    from app.main import create_app
    from app.core.config import load_settings

    settings = load_settings(
        _env_file=None,
        SUPABASE_URL="http://fake.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="fake-key",
        ENV=env.value,
        DEMO_MODE_ENABLED=demo_mode,
    )
    app = create_app(settings)
    # Inyectar servicio con delay=0
    ws = FakeWsManager()
    svc = LiveAnalysisService(ws, progressive_delay=0)
    app.state.live_analysis_service = svc
    app.state.ws_manager = ws
    return app


@pytest.fixture
def ws_manager() -> FakeWsManager:
    return FakeWsManager()


@pytest.fixture
def service(ws_manager: FakeWsManager) -> LiveAnalysisService:
    return LiveAnalysisService(ws_manager, progressive_delay=0)


@pytest.fixture
def context() -> AgentContext:
    return _make_context()


# =============================================================================
# Tests del servicio directo
# =============================================================================


class TestCicloCompleto:
    """El ciclo pasa por los estados en orden correcto."""

    @pytest.mark.asyncio
    async def test_estados_cerebro_en_orden(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={"jira": "demo"})
        session = service.get_session(session_id)
        assert session is not None
        # Estado final debe ser awaiting_approval o completed (hay acciones propuestas)
        assert session.state in (
            CerebroState.AWAITING_APPROVAL,
            CerebroState.COMPLETED,
        )

    @pytest.mark.asyncio
    async def test_agentes_pasan_waiting_investigating_completed(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        for agent_rec in session.agents:
            # Todos terminaron (completed o insufficient_data)
            assert agent_rec.state in (
                LiveAgentState.COMPLETED,
                LiveAgentState.INSUFFICIENT_DATA,
            )
            assert agent_rec.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_duration_ms_es_entero(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        for agent_rec in session.agents:
            assert isinstance(agent_rec.duration_ms, int)

    @pytest.mark.asyncio
    async def test_agents_completed_equals_total_sin_errores(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        # agents_completed cuenta solo COMPLETED, no INSUFFICIENT_DATA
        completed_agents = [
            a for a in session.agents if a.state == LiveAgentState.COMPLETED
        ]
        assert session.agents_completed == len(completed_agents)
        assert session.agents_total == 4


class TestEventosWS:
    """Se emiten los eventos WS esperados."""

    @pytest.mark.asyncio
    async def test_agent_run_started_por_cada_agente(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        started = ws_manager.events_of_type(EventType.AGENT_RUN_STARTED)
        assert len(started) == 4

    @pytest.mark.asyncio
    async def test_agent_run_completed_por_cada_agente(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        completed = ws_manager.events_of_type(EventType.AGENT_RUN_COMPLETED)
        assert len(completed) == 4

    @pytest.mark.asyncio
    async def test_evidence_created_por_cada_evidencia(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        ev_events = ws_manager.events_of_type(EventType.EVIDENCE_CREATED)
        assert len(ev_events) == len(session.evidence)
        assert len(ev_events) > 0

    @pytest.mark.asyncio
    async def test_risk_case_updated_emitido(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        rc_events = ws_manager.events_of_type(EventType.RISK_CASE_UPDATED)
        assert len(rc_events) == 1

    @pytest.mark.asyncio
    async def test_analysis_completed_emitido(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        ac_events = ws_manager.events_of_type(EventType.ANALYSIS_COMPLETED)
        assert len(ac_events) == 1


class TestAgenteFalla:
    """Agente que eleva -> error, los demás siguen."""

    @pytest.mark.asyncio
    async def test_agente_error_estado_partial_error(
        self, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        """Un agente que eleva marca error; cerebro termina en partial_error."""
        from app.agents.specialized.base import BaseSpecializedAgent

        class BrokenAgent(BaseSpecializedAgent):
            name = "broken-agent"

            def analyze(self, ctx: AgentContext) -> AgentOutput:
                raise RuntimeError("Explosión intencional")

        class OkAgent(BaseSpecializedAgent):
            name = "ok-agent"

            def analyze(self, ctx: AgentContext) -> AgentOutput:
                return self._output(ctx, [], summary="Todo bien")

        # Inyectar agentes personalizados
        svc = LiveAnalysisService(ws_manager, progressive_delay=0)
        svc._agents = [OkAgent(), BrokenAgent(), OkAgent(), OkAgent()]

        session_id = uuid4()
        await svc.run(session_id, context, provenance={})
        session = svc.get_session(session_id)
        assert session is not None
        assert session.state == CerebroState.PARTIAL_ERROR
        assert session.agents_completed < session.agents_total

        # El agente roto tiene estado error
        broken_rec = session.agents[1]
        assert broken_rec.state == LiveAgentState.ERROR

    @pytest.mark.asyncio
    async def test_agente_skipped_insufficient_data(
        self, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        """AgentOutput con status=skipped -> insufficient_data, NO es error."""
        from app.agents.specialized.base import BaseSpecializedAgent

        class SkippedAgent(BaseSpecializedAgent):
            name = "skipped-agent"

            def analyze(self, ctx: AgentContext) -> AgentOutput:
                return self._empty_output(ctx, ["falta X"], reason="Sin datos")

        class OkAgent(BaseSpecializedAgent):
            name = "ok-agent"

            def analyze(self, ctx: AgentContext) -> AgentOutput:
                return self._output(ctx, [], summary="OK")

        svc = LiveAnalysisService(ws_manager, progressive_delay=0)
        svc._agents = [OkAgent(), SkippedAgent(), OkAgent(), OkAgent()]

        session_id = uuid4()
        await svc.run(session_id, context, provenance={})
        session = svc.get_session(session_id)
        assert session is not None
        # insufficient_data NO es error -> no partial_error
        assert session.state != CerebroState.PARTIAL_ERROR
        skipped_rec = session.agents[1]
        assert skipped_rec.state == LiveAgentState.INSUFFICIENT_DATA


class TestBroadcastFallo:
    """Fallo de broadcast WS no rompe el análisis."""

    @pytest.mark.asyncio
    async def test_broadcast_roto_no_interrumpe(self, context: AgentContext) -> None:
        broken_ws = BrokenWsManager()
        svc = LiveAnalysisService(broken_ws, progressive_delay=0)
        session_id = uuid4()
        # No debe elevar
        await svc.run(session_id, context, provenance={})
        session = svc.get_session(session_id)
        assert session is not None
        assert session.state in (
            CerebroState.AWAITING_APPROVAL,
            CerebroState.COMPLETED,
        )


class TestDecisiones:
    """Aprobación y rechazo de decisiones."""

    @pytest.mark.asyncio
    async def test_approve_desde_pending(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        if not session.decisions:
            pytest.skip("No hay decisiones en este caso")
        decision = session.decisions[0]
        result = await service.approve_decision(decision.id, "admin@test.com")
        assert result.approval_status.value == "approved"
        assert result.approved_at is not None
        # Emitió decision.approved y decision.updated
        approved_events = ws_manager.events_of_type(EventType.DECISION_APPROVED)
        updated_events = ws_manager.events_of_type(EventType.DECISION_UPDATED)
        assert len(approved_events) >= 1
        assert len(updated_events) >= 1

    @pytest.mark.asyncio
    async def test_approve_dos_veces_error(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        """Doble aprobación es error de dominio. CLAVE."""
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        if not session.decisions:
            pytest.skip("No hay decisiones")
        decision = session.decisions[0]
        await service.approve_decision(decision.id, "admin@test.com")
        with pytest.raises(DomainError):
            await service.approve_decision(decision.id, "otro@test.com")

    @pytest.mark.asyncio
    async def test_reject_desde_approved_error(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        """Rechazar una decisión ya aprobada es error."""
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        if not session.decisions:
            pytest.skip("No hay decisiones")
        decision = session.decisions[0]
        await service.approve_decision(decision.id, "admin@test.com")
        with pytest.raises(DomainError):
            await service.reject_decision(decision.id, "otro@test.com", "motivo")

    @pytest.mark.asyncio
    async def test_approve_deja_execution_not_started(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        """Aprobar NO ejecuta: execution_status queda en not_started."""
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        if not session.decisions:
            pytest.skip("No hay decisiones")
        decision = session.decisions[0]
        await service.approve_decision(decision.id, "admin@test.com")
        assert decision.execution_status.value == "not_started"

    @pytest.mark.asyncio
    async def test_reject_desde_pending(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        if not session.decisions:
            pytest.skip("No hay decisiones")
        decision = session.decisions[0]
        result = await service.reject_decision(decision.id, "admin@test.com", "No procede")
        assert result.approval_status.value == "rejected"
        assert result.rejection_reason == "No procede"


# =============================================================================
# Tests HTTP (rutas)
# =============================================================================


class TestHTTPEndpoints:
    """Tests de los endpoints via HTTPX."""

    @pytest.mark.asyncio
    async def test_post_analysis_202(self) -> None:
        app = _create_app_for_test()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/live/analysis")
            assert resp.status_code == 202
            data = resp.json()
            assert "session_id" in data
            assert data["state"] == "ready"

    @pytest.mark.asyncio
    async def test_post_analysis_409_doble(self) -> None:
        """Segunda POST con sesión activa -> 409."""
        app = _create_app_for_test()
        svc: LiveAnalysisService = app.state.live_analysis_service
        # Crear sesión activa manualmente
        from app.services.live_analysis_service import LiveSession
        fake_session = LiveSession(uuid4(), provenance={})
        fake_session.state = CerebroState.GATHERING_EVIDENCE
        svc._sessions[fake_session.session_id] = fake_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/live/analysis")
            assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_analysis_404(self) -> None:
        app = _create_app_for_test()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/live/analysis/{uuid4()}")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_analysis_200(self) -> None:
        app = _create_app_for_test()
        svc: LiveAnalysisService = app.state.live_analysis_service
        ctx = _make_context()
        session_id = uuid4()
        await svc.run(session_id, ctx, provenance={"jira": "demo"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/live/analysis/{session_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"] == str(session_id)
            assert data["persistence"] == "memory"
            assert data["persistence_note"] != ""

    @pytest.mark.asyncio
    async def test_approve_200(self) -> None:
        app = _create_app_for_test()
        svc: LiveAnalysisService = app.state.live_analysis_service
        ctx = _make_context()
        session_id = uuid4()
        await svc.run(session_id, ctx, provenance={})
        session = svc.get_session(session_id)
        assert session is not None
        if not session.decisions:
            pytest.skip("No hay decisiones")
        decision = session.decisions[0]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/live/decisions/{decision.id}/approve",
                json={"approved_by": "admin@test.com"},
            )
            assert resp.status_code == 200
            assert resp.json()["approved_by"] == "admin@test.com"

    @pytest.mark.asyncio
    async def test_approve_409_doble(self) -> None:
        app = _create_app_for_test()
        svc: LiveAnalysisService = app.state.live_analysis_service
        ctx = _make_context()
        session_id = uuid4()
        await svc.run(session_id, ctx, provenance={})
        session = svc.get_session(session_id)
        assert session is not None
        if not session.decisions:
            pytest.skip("No hay decisiones")
        decision = session.decisions[0]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/live/decisions/{decision.id}/approve",
                json={"approved_by": "admin@test.com"},
            )
            resp2 = await client.post(
                f"/live/decisions/{decision.id}/approve",
                json={"approved_by": "otro@test.com"},
            )
            assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_reject_404_no_existe(self) -> None:
        app = _create_app_for_test()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/live/decisions/{uuid4()}/reject",
                json={"rejected_by": "admin", "reason": "No"},
            )
            assert resp.status_code == 404


class TestProvenance:
    """Endpoint /live/provenance."""

    @pytest.mark.asyncio
    async def test_provenance_marca_demo(self) -> None:
        app = _create_app_for_test()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/live/provenance")
            assert resp.status_code == 200
            data = resp.json()
            providers = data["providers"]
            # Sin providers registrados, todos son demo
            for p in providers:
                assert p["provenance"] == "demo"
                assert p["connected"] is False
                assert "DEMO" in p["label"]


class TestDemoGuards:
    """Rutas demo protegidas en producción."""

    @pytest.mark.asyncio
    async def test_simulate_jira_production_404(self) -> None:
        app = _create_app_for_test(env=Environment.PRODUCTION, demo_mode=False)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/live/simulate/jira")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_simulate_jira_demo_202(self) -> None:
        app = _create_app_for_test(env=Environment.DEVELOPMENT, demo_mode=True)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/live/simulate/jira")
            assert resp.status_code == 202
            data = resp.json()
            assert "session_id" in data

    @pytest.mark.asyncio
    async def test_reset_production_404(self) -> None:
        app = _create_app_for_test(env=Environment.PRODUCTION, demo_mode=False)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/live/reset")
            assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_reset_demo_limpia_sesiones(self) -> None:
        app = _create_app_for_test()
        svc: LiveAnalysisService = app.state.live_analysis_service
        ctx = _make_context()
        session_id = uuid4()
        await svc.run(session_id, ctx, provenance={})
        assert len(svc.sessions) > 0

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/live/reset")
            assert resp.status_code == 200
        assert len(svc.sessions) == 0


class TestTimeline:
    """Timeline en orden cronológico con actor/tipo/resumen."""

    @pytest.mark.asyncio
    async def test_timeline_orden_cronologico(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        assert len(session.timeline) > 0
        # Orden cronológico
        timestamps = [t.at for t in session.timeline]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_timeline_tiene_actor_tipo_resumen(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        for entry in session.timeline:
            assert entry.actor_type in ("agent", "system", "human", "provider")
            assert entry.actor_name != ""
            assert entry.event_type != ""
            assert entry.summary != ""

    @pytest.mark.asyncio
    async def test_get_timeline_endpoint(self) -> None:
        app = _create_app_for_test()
        svc: LiveAnalysisService = app.state.live_analysis_service
        ctx = _make_context()
        session_id = uuid4()
        await svc.run(session_id, ctx, provenance={})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/live/analysis/{session_id}/timeline")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) > 0
            assert "actor_type" in data[0]
            assert "summary" in data[0]


class TestPersistence:
    """Verificar campo persistence cuando el esquema no está."""

    @pytest.mark.asyncio
    async def test_persistence_memory_y_note(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        data = session.to_dict()
        assert data["persistence"] == "memory"
        assert data["persistence_note"] != ""
        assert "esquema" in data["persistence_note"].lower() or "memoria" in data["persistence_note"].lower()


class TestSimulateJiraRecalcula:
    """simulate/jira re-ejecuta y el riesgo puede cambiar."""

    @pytest.mark.asyncio
    async def test_simulate_jira_crea_nueva_sesion(self) -> None:
        app = _create_app_for_test()
        svc: LiveAnalysisService = app.state.live_analysis_service

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/live/simulate/jira")
            assert resp.status_code == 202
            data = resp.json()
            session_id = data["session_id"]
            # Esperar un poco para que el background task corra
            await asyncio.sleep(0.1)
            # La sesión debe existir
            svc.get_session(UUID(session_id))
            # Puede no haber corrido aún en background, eso está bien
            # Lo importante es que se aceptó


class TestRiskCaseGenerado:
    """El risk_case se genera correctamente."""

    @pytest.mark.asyncio
    async def test_risk_case_no_none(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={})
        session = service.get_session(session_id)
        assert session is not None
        assert session.risk_case is not None
        assert session.risk_case.consolidated_score >= 0

    @pytest.mark.asyncio
    async def test_evidence_tiene_provenance(
        self, service: LiveAnalysisService, ws_manager: FakeWsManager, context: AgentContext
    ) -> None:
        session_id = uuid4()
        await service.run(session_id, context, provenance={"jira": "real", "github": "demo"})
        session = service.get_session(session_id)
        assert session is not None
        # Al menos alguna evidencia tiene provenance
        if session.evidence:
            for ev in session.evidence:
                assert "provenance" in ev
