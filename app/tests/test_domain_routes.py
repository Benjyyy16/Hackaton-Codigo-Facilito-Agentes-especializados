"""Tests de las rutas HTTP del dominio Datgent.

Patrón: httpx.ASGITransport + dependency_overrides. No red, no BD real.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import (
    DomainRepositoryBundle,
    get_analysis_service,
    get_decision_service,
    get_domain_repositories,
    get_ws_manager,
)
from app.core.config import Settings
from app.main import create_app
from app.repositories.base import Page, Row
from app.services.analysis_service import AnalysisService
from app.services.decision_service import (
    ActionNotExecutableError,
    DecisionService,
    DecisionStateError,
)
from app.tests.conftest import build_settings
from app.websocket.manager import ConnectionManager


# --- Helpers -------------------------------------------------------------------

NOW_ISO = datetime.now(UTC).isoformat()


def _project_row(project_id: UUID | None = None) -> Row:
    pid = str(project_id or uuid4())
    return {
        "id": pid,
        "name": "Proyecto Test",
        "description": "desc",
        "status": "active",
        "external_references": {},
        "hourly_cost": "50.00",
        "currency": "USD",
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    }


def _commitment_row(commitment_id: UUID | None = None, project_id: UUID | None = None) -> Row:
    return {
        "id": str(commitment_id or uuid4()),
        "project_id": str(project_id or uuid4()),
        "title": "Compromiso Test",
        "description": "desc",
        "beneficiary": "Cliente",
        "owner": "Dev",
        "due_date": NOW_ISO,
        "financial_exposure": "1000.00",
        "currency": "USD",
        "priority": "high",
        "status": "open",
        "source": "manual",
        "metadata": {},
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    }


def _risk_case_row(risk_case_id: UUID | None = None, commitment_id: UUID | None = None) -> Row:
    return {
        "id": str(risk_case_id or uuid4()),
        "commitment_id": str(commitment_id or uuid4()),
        "consolidated_score": 75,
        "severity": "high",
        "confidence": 0.9,
        "causal_chain": [],
        "premortem": {},
        "scenarios": [],
        "facts": [],
        "inferences": [],
        "assumptions": [],
        "missing_information": [],
        "summary": "Riesgo alto",
        "is_partial": False,
        "status": "open",
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    }


def _alert_row(alert_id: UUID | None = None) -> Row:
    return {
        "id": str(alert_id or uuid4()),
        "risk_case_id": str(uuid4()),
        "commitment_id": str(uuid4()),
        "severity": "high",
        "title": "Alerta Test",
        "description": "desc",
        "status": "open",
        "acknowledged_by": None,
        "acknowledged_at": None,
        "resolved_at": None,
        "created_at": NOW_ISO,
    }


def _decision_row(decision_id: UUID | None = None, approval_status: str = "pending") -> Row:
    return {
        "id": str(decision_id or uuid4()),
        "risk_case_id": str(uuid4()),
        "commitment_id": str(uuid4()),
        "action_type": "update_jira_issue",
        "title": "Actualizar Jira",
        "rationale": "Razón",
        "proposed_payload": {},
        "approval_status": approval_status,
        "requested_by": "orchestrator-agent",
        "approved_by": None,
        "approved_at": None,
        "rejection_reason": None,
        "execution_status": "not_started",
        "execution_result": {},
        "executed_at": None,
        "error": None,
        "created_at": NOW_ISO,
    }


def _agent_run_row(run_id: UUID | None = None) -> Row:
    return {
        "id": str(run_id or uuid4()),
        "agent_name": "jira_agent",
        "commitment_id": str(uuid4()),
        "status": "completed",
        "started_at": NOW_ISO,
        "finished_at": NOW_ISO,
        "model": "gpt-4",
        "prompt_version": "1.0",
        "input_reference": "commitment:xyz",
        "output": {"risk_score": 50},
        "error": None,
        "duration_ms": 120,
        "created_at": NOW_ISO,
    }


def _timeline_row() -> Row:
    return {
        "id": str(uuid4()),
        "commitment_id": str(uuid4()),
        "actor_type": "agent",
        "actor_name": "orchestrator",
        "event_type": "analysis.completed",
        "summary": "Análisis completado",
        "payload": {},
        "created_at": NOW_ISO,
    }


# --- Fake repos ----------------------------------------------------------------

from app.core.exceptions import EntityNotFoundError


class FakeRepo:
    """Repo falso genérico que simula list_page, get_or_raise, create, update."""

    def __init__(self, rows: list[Row] | None = None) -> None:
        self._rows = rows or []
        self._not_found = False

    def set_not_found(self) -> None:
        self._not_found = True

    async def list_page(self, *, limit: int = 20, offset: int = 0, **kwargs: Any) -> Page[Row]:
        return Page(self._rows, total=len(self._rows), limit=limit, offset=offset)

    async def get_or_raise(self, entity_id: UUID) -> Row:
        if self._not_found or not self._rows:
            raise EntityNotFoundError(details={"id": str(entity_id)})
        return self._rows[0]

    async def get(self, entity_id: UUID) -> Row | None:
        if self._not_found or not self._rows:
            return None
        return self._rows[0]

    async def create(self, payload: Row) -> Row:
        row = {**payload, "id": str(uuid4()), "created_at": NOW_ISO, "updated_at": NOW_ISO}
        return row

    async def update(self, entity_id: UUID, payload: Row) -> Row:
        if self._not_found or not self._rows:
            raise EntityNotFoundError(details={"id": str(entity_id)})
        return {**self._rows[0], **payload}

    async def acknowledge(self, alert_id: UUID, acknowledged_by: str) -> Row:
        if not self._rows:
            raise EntityNotFoundError(details={"id": str(alert_id)})
        return {**self._rows[0], "status": "acknowledged", "acknowledged_by": acknowledged_by}

    async def list_for_commitment(self, commitment_id: UUID, **kwargs: Any) -> list[Row]:
        return self._rows


# --- Fake services -------------------------------------------------------------


class FakeAnalysisService:
    """Stub de AnalysisService que no ejecuta nada."""

    def __init__(self) -> None:
        self.called_with: UUID | None = None

    async def analyze_commitment(self, commitment_id: UUID, **kwargs: Any) -> None:
        self.called_with = commitment_id


class FakeDecisionService:
    """Stub de DecisionService con control de errores."""

    def __init__(self, *, state_error: bool = False, not_executable: bool = False) -> None:
        self._state_error = state_error
        self._not_executable = not_executable
        self._row = _decision_row()

    async def approve(self, decision_id: UUID, approved_by: str) -> Row:
        if self._state_error:
            raise DecisionStateError("Ya aprobada")
        return {**self._row, "approval_status": "approved", "approved_by": approved_by}

    async def reject(self, decision_id: UUID, rejected_by: str, reason: str) -> Row:
        if self._state_error:
            raise DecisionStateError("Ya rechazada")
        return {**self._row, "approval_status": "rejected"}

    async def execute(self, decision_id: UUID, executed_by: str) -> Row:
        if self._state_error:
            raise DecisionStateError("No aprobada")
        if self._not_executable:
            raise ActionNotExecutableError("Sin ejecutor")
        return {**self._row, "execution_status": "succeeded"}


# --- App factory para tests ----------------------------------------------------


def _build_app(
    repos: DomainRepositoryBundle,
    analysis_service: Any = None,
    decision_service: Any = None,
) -> FastAPI:
    settings = build_settings()
    app = create_app(settings)
    # Sin lifespan: state manual
    app.state.storage = None
    app.state.ws_manager = ConnectionManager()

    app.dependency_overrides[get_domain_repositories] = lambda: repos
    app.dependency_overrides[get_ws_manager] = lambda: app.state.ws_manager
    if analysis_service is not None:
        app.dependency_overrides[get_analysis_service] = lambda: analysis_service
    if decision_service is not None:
        app.dependency_overrides[get_decision_service] = lambda: decision_service
    return app


@asynccontextmanager
async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _repos(
    projects: list[Row] | None = None,
    commitments: list[Row] | None = None,
    risk_cases: list[Row] | None = None,
    alerts: list[Row] | None = None,
    decisions: list[Row] | None = None,
    agent_runs: list[Row] | None = None,
    findings: list[Row] | None = None,
    timeline: list[Row] | None = None,
    not_found: set[str] | None = None,
) -> DomainRepositoryBundle:
    nf = not_found or set()

    def _make(rows: list[Row] | None, name: str) -> FakeRepo:
        repo = FakeRepo(rows)
        if name in nf:
            repo.set_not_found()
        return repo

    return DomainRepositoryBundle(
        projects=_make(projects, "projects"),  # type: ignore[arg-type]
        commitments=_make(commitments, "commitments"),  # type: ignore[arg-type]
        source_events=_make(None, "source_events"),  # type: ignore[arg-type]
        agent_runs=_make(agent_runs, "agent_runs"),  # type: ignore[arg-type]
        findings=_make(findings, "findings"),  # type: ignore[arg-type]
        evidence=_make(None, "evidence"),  # type: ignore[arg-type]
        risk_cases=_make(risk_cases, "risk_cases"),  # type: ignore[arg-type]
        alerts=_make(alerts, "alerts"),  # type: ignore[arg-type]
        decisions=_make(decisions, "decisions"),  # type: ignore[arg-type]
        timeline=_make(timeline, "timeline"),  # type: ignore[arg-type]
        documents=_make(None, "documents"),  # type: ignore[arg-type]
    )


# =============================================================================
# TESTS
# =============================================================================


class TestReadyEndpoint:
    async def test_ready_returns_200_when_storage_connected(self) -> None:
        settings = build_settings()
        app = create_app(settings)
        # Simular storage conectado
        class FakeStorage:
            is_connected = True
        app.state.storage = FakeStorage()

        async with _client(app) as c:
            r = await c.get("/ready")
        assert r.status_code == 200
        assert r.json()["ready"] is True

    async def test_ready_returns_503_when_storage_not_connected(self) -> None:
        settings = build_settings()
        app = create_app(settings)
        app.state.storage = None

        async with _client(app) as c:
            r = await c.get("/ready")
        assert r.status_code == 503
        assert r.json()["ready"] is False


class TestProjectRoutes:
    async def test_list_projects_200(self) -> None:
        app = _build_app(_repos(projects=[_project_row()]))
        async with _client(app) as c:
            r = await c.get("/projects")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_list_projects_pagination(self) -> None:
        rows = [_project_row() for _ in range(3)]
        app = _build_app(_repos(projects=rows))
        async with _client(app) as c:
            r = await c.get("/projects?limit=2&offset=0")
        assert r.status_code == 200

    async def test_create_project_201(self) -> None:
        app = _build_app(_repos(projects=[_project_row()]))
        async with _client(app) as c:
            r = await c.post("/projects", json={"name": "Nuevo"})
        assert r.status_code == 201
        assert "id" in r.json()

    async def test_get_project_200(self) -> None:
        pid = uuid4()
        app = _build_app(_repos(projects=[_project_row(pid)]))
        async with _client(app) as c:
            r = await c.get(f"/projects/{pid}")
        assert r.status_code == 200

    async def test_get_project_404(self) -> None:
        app = _build_app(_repos(not_found={"projects"}))
        async with _client(app) as c:
            r = await c.get(f"/projects/{uuid4()}")
        assert r.status_code == 404


class TestCommitmentRoutes:
    async def test_list_commitments_200(self) -> None:
        app = _build_app(_repos(commitments=[_commitment_row()]))
        async with _client(app) as c:
            r = await c.get("/commitments")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_list_commitments_filter_project(self) -> None:
        pid = uuid4()
        app = _build_app(_repos(commitments=[_commitment_row(project_id=pid)]))
        async with _client(app) as c:
            r = await c.get(f"/commitments?project_id={pid}")
        assert r.status_code == 200

    async def test_list_commitments_filter_status(self) -> None:
        app = _build_app(_repos(commitments=[_commitment_row()]))
        async with _client(app) as c:
            r = await c.get("/commitments?status=open")
        assert r.status_code == 200

    async def test_create_commitment_201(self) -> None:
        app = _build_app(_repos(commitments=[_commitment_row()]))
        async with _client(app) as c:
            r = await c.post("/commitments", json={
                "project_id": str(uuid4()),
                "title": "Nuevo compromiso",
            })
        assert r.status_code == 201

    async def test_get_commitment_200(self) -> None:
        cid = uuid4()
        app = _build_app(_repos(commitments=[_commitment_row(cid)]))
        async with _client(app) as c:
            r = await c.get(f"/commitments/{cid}")
        assert r.status_code == 200

    async def test_get_commitment_404(self) -> None:
        app = _build_app(_repos(not_found={"commitments"}))
        async with _client(app) as c:
            r = await c.get(f"/commitments/{uuid4()}")
        assert r.status_code == 404

    async def test_patch_commitment_200(self) -> None:
        cid = uuid4()
        app = _build_app(_repos(commitments=[_commitment_row(cid)]))
        async with _client(app) as c:
            r = await c.patch(f"/commitments/{cid}", json={"title": "Nuevo título"})
        assert r.status_code == 200

    async def test_patch_commitment_404(self) -> None:
        app = _build_app(_repos(not_found={"commitments"}))
        async with _client(app) as c:
            r = await c.patch(f"/commitments/{uuid4()}", json={"title": "x"})
        assert r.status_code == 404

    async def test_analyze_commitment_202(self) -> None:
        cid = uuid4()
        fake_svc = FakeAnalysisService()
        app = _build_app(
            _repos(commitments=[_commitment_row(cid)]),
            analysis_service=fake_svc,
        )
        async with _client(app) as c:
            r = await c.post(f"/commitments/{cid}/analyze")
        assert r.status_code == 202
        assert r.json()["status"] == "accepted"

    async def test_analyze_commitment_404_if_not_found(self) -> None:
        fake_svc = FakeAnalysisService()
        app = _build_app(
            _repos(not_found={"commitments"}),
            analysis_service=fake_svc,
        )
        async with _client(app) as c:
            r = await c.post(f"/commitments/{uuid4()}/analyze")
        assert r.status_code == 404

    async def test_findings_200(self) -> None:
        cid = uuid4()
        app = _build_app(_repos(
            commitments=[_commitment_row(cid)],
            findings=[{"id": str(uuid4()), "category": "schedule", "summary": "Late"}],
        ))
        async with _client(app) as c:
            r = await c.get(f"/commitments/{cid}/findings")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_timeline_200(self) -> None:
        cid = uuid4()
        app = _build_app(_repos(
            commitments=[_commitment_row(cid)],
            timeline=[_timeline_row()],
        ))
        async with _client(app) as c:
            r = await c.get(f"/commitments/{cid}/timeline")
        assert r.status_code == 200


class TestRiskCaseRoutes:
    async def test_list_risk_cases_200(self) -> None:
        app = _build_app(_repos(risk_cases=[_risk_case_row()]))
        async with _client(app) as c:
            r = await c.get("/risk-cases")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_get_risk_case_200(self) -> None:
        rcid = uuid4()
        app = _build_app(_repos(risk_cases=[_risk_case_row(rcid)]))
        async with _client(app) as c:
            r = await c.get(f"/risk-cases/{rcid}")
        assert r.status_code == 200

    async def test_get_risk_case_404(self) -> None:
        app = _build_app(_repos(not_found={"risk_cases"}))
        async with _client(app) as c:
            r = await c.get(f"/risk-cases/{uuid4()}")
        assert r.status_code == 404

    async def test_reanalyze_202(self) -> None:
        rcid = uuid4()
        cid = uuid4()
        fake_svc = FakeAnalysisService()
        app = _build_app(
            _repos(risk_cases=[_risk_case_row(rcid, cid)]),
            analysis_service=fake_svc,
        )
        async with _client(app) as c:
            r = await c.post(f"/risk-cases/{rcid}/reanalyze")
        assert r.status_code == 202

    async def test_reanalyze_404(self) -> None:
        fake_svc = FakeAnalysisService()
        app = _build_app(
            _repos(not_found={"risk_cases"}),
            analysis_service=fake_svc,
        )
        async with _client(app) as c:
            r = await c.post(f"/risk-cases/{uuid4()}/reanalyze")
        assert r.status_code == 404


class TestAlertRoutes:
    async def test_list_alerts_200(self) -> None:
        app = _build_app(_repos(alerts=[_alert_row()]))
        async with _client(app) as c:
            r = await c.get("/alerts")
        assert r.status_code == 200

    async def test_list_alerts_filter_status(self) -> None:
        app = _build_app(_repos(alerts=[_alert_row()]))
        async with _client(app) as c:
            r = await c.get("/alerts?status=open")
        assert r.status_code == 200

    async def test_list_alerts_filter_severity(self) -> None:
        app = _build_app(_repos(alerts=[_alert_row()]))
        async with _client(app) as c:
            r = await c.get("/alerts?severity=high")
        assert r.status_code == 200

    async def test_acknowledge_alert_200(self) -> None:
        aid = uuid4()
        app = _build_app(_repos(alerts=[_alert_row(aid)]))
        async with _client(app) as c:
            r = await c.patch(
                f"/alerts/{aid}/acknowledge",
                json={"acknowledged_by": "admin"},
            )
        assert r.status_code == 200
        assert r.json()["status"] == "acknowledged"

    async def test_acknowledge_alert_404(self) -> None:
        app = _build_app(_repos(not_found={"alerts"}))
        async with _client(app) as c:
            r = await c.patch(
                f"/alerts/{uuid4()}/acknowledge",
                json={"acknowledged_by": "admin"},
            )
        assert r.status_code == 404


class TestDecisionRoutes:
    async def test_list_decisions_200(self) -> None:
        app = _build_app(
            _repos(decisions=[_decision_row()]),
            decision_service=FakeDecisionService(),
        )
        async with _client(app) as c:
            r = await c.get("/decisions")
        assert r.status_code == 200

    async def test_list_decisions_filter_approval_status(self) -> None:
        app = _build_app(
            _repos(decisions=[_decision_row()]),
            decision_service=FakeDecisionService(),
        )
        async with _client(app) as c:
            r = await c.get("/decisions?approval_status=pending")
        assert r.status_code == 200

    async def test_approve_decision_200(self) -> None:
        did = uuid4()
        app = _build_app(
            _repos(decisions=[_decision_row(did)]),
            decision_service=FakeDecisionService(),
        )
        async with _client(app) as c:
            r = await c.post(
                f"/decisions/{did}/approve",
                json={"approved_by": "manager"},
            )
        assert r.status_code == 200

    async def test_approve_decision_409(self) -> None:
        did = uuid4()
        app = _build_app(
            _repos(decisions=[_decision_row(did, "approved")]),
            decision_service=FakeDecisionService(state_error=True),
        )
        async with _client(app) as c:
            r = await c.post(
                f"/decisions/{did}/approve",
                json={"approved_by": "manager"},
            )
        assert r.status_code == 409

    async def test_reject_decision_200(self) -> None:
        did = uuid4()
        app = _build_app(
            _repos(decisions=[_decision_row(did)]),
            decision_service=FakeDecisionService(),
        )
        async with _client(app) as c:
            r = await c.post(
                f"/decisions/{did}/reject",
                json={"rejected_by": "manager", "reason": "No prioritario"},
            )
        assert r.status_code == 200

    async def test_reject_decision_409(self) -> None:
        did = uuid4()
        app = _build_app(
            _repos(decisions=[_decision_row(did, "approved")]),
            decision_service=FakeDecisionService(state_error=True),
        )
        async with _client(app) as c:
            r = await c.post(
                f"/decisions/{did}/reject",
                json={"rejected_by": "manager", "reason": "ya"},
            )
        assert r.status_code == 409

    async def test_execute_decision_200(self) -> None:
        did = uuid4()
        app = _build_app(
            _repos(decisions=[_decision_row(did, "approved")]),
            decision_service=FakeDecisionService(),
        )
        async with _client(app) as c:
            r = await c.post(f"/decisions/{did}/execute")
        assert r.status_code == 200

    async def test_execute_decision_409_not_approved(self) -> None:
        did = uuid4()
        app = _build_app(
            _repos(decisions=[_decision_row(did)]),
            decision_service=FakeDecisionService(state_error=True),
        )
        async with _client(app) as c:
            r = await c.post(f"/decisions/{did}/execute")
        assert r.status_code == 409

    async def test_execute_decision_422_no_executor(self) -> None:
        did = uuid4()
        app = _build_app(
            _repos(decisions=[_decision_row(did, "approved")]),
            decision_service=FakeDecisionService(not_executable=True),
        )
        async with _client(app) as c:
            r = await c.post(f"/decisions/{did}/execute")
        assert r.status_code == 422


class TestAgentRunRoutes:
    async def test_get_agent_run_200(self) -> None:
        rid = uuid4()
        app = _build_app(_repos(agent_runs=[_agent_run_row(rid)]))
        async with _client(app) as c:
            r = await c.get(f"/agent-runs/{rid}")
        assert r.status_code == 200
        assert r.json()["agent_name"] == "jira_agent"

    async def test_get_agent_run_404(self) -> None:
        app = _build_app(_repos(not_found={"agent_runs"}))
        async with _client(app) as c:
            r = await c.get(f"/agent-runs/{uuid4()}")
        assert r.status_code == 404


class TestAgentsStatusRoute:
    async def test_agents_status_200(self) -> None:
        """GET /agents/status devuelve 200 con la lista (puede estar vacía)."""
        settings = build_settings()
        app = create_app(settings)
        # Sin providers registrados
        from app.providers.registry import ProviderRegistry
        app.state.providers = ProviderRegistry()
        app.state.storage = None

        async with _client(app) as c:
            r = await c.get("/agents/status")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
