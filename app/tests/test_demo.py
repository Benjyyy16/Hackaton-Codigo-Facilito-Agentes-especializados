"""Tests del caso demo y rutas /demo.

Valida:
- Seed crea las entidades correctas.
- Seed es IDEMPOTENTE (dos veces no duplica).
- Simulate dispara análisis y responde 202.
- Reset borra solo datos demo.
- En ENV=production sin bandera las 3 rutas dan 404.
- Con DEMO_MODE_ENABLED=true en production SÍ funcionan.
- El caso demo produce score >= 80 y severity critical (reproducibilidad).
"""

from __future__ import annotations


import pytest

from app.providers.registry import ProviderRegistry
from app.services.demo_service import (
    DEMO_COMMITMENT_ID,
    DEMO_DOCUMENT_IDS,
    DEMO_EVENT_IDS,
    DEMO_PROJECT_ID,
    DemoService,
)
from app.tests.conftest import build_settings, client_for, StubStorage
from app.tests.fakes.supabase import FakeSupabaseClient


# --- Fixtures -----------------------------------------------------------------------

FAKE_PROJECT_ROW = {
    "id": str(DEMO_PROJECT_ID),
    "name": "Pagos Empresariales",
    "description": "Integración de pasarela de pagos",
    "status": "active",
    "external_references": {"jira": "DAT"},
    "hourly_cost": "75.00",
    "currency": "USD",
    "created_at": "2026-07-20T00:00:00Z",
    "updated_at": "2026-07-20T00:00:00Z",
}

FAKE_COMMITMENT_ROW = {
    "id": str(DEMO_COMMITMENT_ID),
    "project_id": str(DEMO_PROJECT_ID),
    "title": "Entregar integración de pagos empresariales antes del viernes",
    "beneficiary": "Cliente Enterprise",
    "financial_exposure": "20000",
    "status": "at_risk",
    "due_date": "2026-07-24T23:59:59Z",
    "currency": "USD",
    "priority": "critical",
    "source": "demo",
    "metadata": {},
    "created_at": "2026-07-20T00:00:00Z",
    "updated_at": "2026-07-20T00:00:00Z",
}


@pytest.fixture
def fake_client() -> FakeSupabaseClient:
    return FakeSupabaseClient()


def _make_app(fake_client: FakeSupabaseClient, *, env: str = "test", demo_enabled: bool = False):
    from app.main import create_app

    settings = build_settings(ENV=env, DEMO_MODE_ENABLED=demo_enabled)
    application = create_app(settings)
    storage = StubStorage(settings, fake_client)
    application.state.storage = storage
    application.state.providers = ProviderRegistry()
    return application


@pytest.fixture
def app_dev(fake_client: FakeSupabaseClient):
    """App en development (demo accesible)."""
    return _make_app(fake_client, env="development")


@pytest.fixture
def app_test(fake_client: FakeSupabaseClient):
    """App en test (demo accesible)."""
    return _make_app(fake_client, env="test")


@pytest.fixture
def app_prod(fake_client: FakeSupabaseClient):
    """App en production SIN bandera (demo bloqueado)."""
    return _make_app(fake_client, env="production")


@pytest.fixture
def app_prod_enabled(fake_client: FakeSupabaseClient):
    """App en production CON DEMO_MODE_ENABLED=true."""
    return _make_app(fake_client, env="production", demo_enabled=True)


# --- Tests de acceso por entorno ----------------------------------------------------


@pytest.mark.asyncio
async def test_seed_404_in_production(app_prod, fake_client: FakeSupabaseClient):
    """POST /demo/seed en production sin bandera → 404."""
    async with client_for(app_prod) as client:
        resp = await client.post("/demo/seed")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_simulate_404_in_production(app_prod, fake_client: FakeSupabaseClient):
    """POST /demo/simulate en production sin bandera → 404."""
    async with client_for(app_prod) as client:
        resp = await client.post("/demo/simulate")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reset_404_in_production(app_prod, fake_client: FakeSupabaseClient):
    """DELETE /demo/reset en production sin bandera → 404."""
    async with client_for(app_prod) as client:
        resp = await client.delete("/demo/reset")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_seed_works_in_development(app_dev, fake_client: FakeSupabaseClient):
    """POST /demo/seed en development → 201."""
    fake_client.for_table("projects").returns([FAKE_PROJECT_ROW])
    fake_client.for_table("commitments").returns([FAKE_COMMITMENT_ROW])
    fake_client.for_table("source_events").returns([{"id": str(DEMO_EVENT_IDS[0])}])
    fake_client.for_table("documents").returns([{"id": str(DEMO_DOCUMENT_IDS[0])}])
    async with client_for(app_dev) as client:
        resp = await client.post("/demo/seed")
    assert resp.status_code == 201
    data = resp.json()
    assert data["project_id"] == str(DEMO_PROJECT_ID)
    assert data["commitment_id"] == str(DEMO_COMMITMENT_ID)


@pytest.mark.asyncio
async def test_seed_works_in_test_env(app_test, fake_client: FakeSupabaseClient):
    """POST /demo/seed en test → 201."""
    fake_client.for_table("projects").returns([FAKE_PROJECT_ROW])
    fake_client.for_table("commitments").returns([FAKE_COMMITMENT_ROW])
    fake_client.for_table("source_events").returns([{"id": str(DEMO_EVENT_IDS[0])}])
    fake_client.for_table("documents").returns([{"id": str(DEMO_DOCUMENT_IDS[0])}])
    async with client_for(app_test) as client:
        resp = await client.post("/demo/seed")
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_seed_works_in_production_with_flag(app_prod_enabled, fake_client: FakeSupabaseClient):
    """POST /demo/seed en production con DEMO_MODE_ENABLED=true → 201."""
    fake_client.for_table("projects").returns([FAKE_PROJECT_ROW])
    fake_client.for_table("commitments").returns([FAKE_COMMITMENT_ROW])
    fake_client.for_table("source_events").returns([{"id": str(DEMO_EVENT_IDS[0])}])
    fake_client.for_table("documents").returns([{"id": str(DEMO_DOCUMENT_IDS[0])}])
    async with client_for(app_prod_enabled) as client:
        resp = await client.post("/demo/seed")
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_simulate_works_in_production_with_flag(app_prod_enabled, fake_client: FakeSupabaseClient):
    """POST /demo/simulate en production con DEMO_MODE_ENABLED=true → 202."""
    fake_client.for_table("projects").returns([FAKE_PROJECT_ROW])
    fake_client.for_table("commitments").returns([FAKE_COMMITMENT_ROW])
    fake_client.for_table("source_events").returns([{"id": str(DEMO_EVENT_IDS[0])}])
    fake_client.for_table("documents").returns([{"id": str(DEMO_DOCUMENT_IDS[0])}])
    fake_client.for_table("agent_runs").returns([{"id": "00000000-0000-4000-8000-000000000099"}])
    fake_client.for_table("risk_cases").returns([{"id": "00000000-0000-4000-8000-000000000098"}])
    fake_client.for_table("findings").returns([])
    fake_client.for_table("evidence").returns([])
    fake_client.for_table("alerts").returns([])
    fake_client.for_table("decisions").returns([])
    fake_client.for_table("timeline_events").returns([])
    async with client_for(app_prod_enabled) as client:
        resp = await client.post("/demo/simulate")
    assert resp.status_code == 202
    assert "analysis_triggered" in resp.json()["status"]


@pytest.mark.asyncio
async def test_reset_works_in_production_with_flag(app_prod_enabled, fake_client: FakeSupabaseClient):
    """DELETE /demo/reset en production con DEMO_MODE_ENABLED=true → 200."""
    # delete devuelve []
    fake_client.for_table("documents").returns([])
    fake_client.for_table("source_events").returns([])
    fake_client.for_table("commitments").returns([])
    fake_client.for_table("projects").returns([])
    async with client_for(app_prod_enabled) as client:
        resp = await client.delete("/demo/reset")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cleaned"


# --- Tests de DemoService directos --------------------------------------------------


@pytest.mark.asyncio
async def test_seed_is_idempotent(fake_client: FakeSupabaseClient):
    """Ejecutar seed dos veces no duplica: usa upsert."""
    from app.repositories.domain import (
        CommitmentRepository,
        DocumentRepository,
        ProjectRepository,
        SourceEventRepository,
    )

    fake_client.for_table("projects").returns([FAKE_PROJECT_ROW])
    fake_client.for_table("commitments").returns([FAKE_COMMITMENT_ROW])
    fake_client.for_table("source_events").returns([{"id": str(DEMO_EVENT_IDS[0])}])
    fake_client.for_table("documents").returns([{"id": str(DEMO_DOCUMENT_IDS[0])}])

    svc = DemoService(
        projects=ProjectRepository(fake_client),
        commitments=CommitmentRepository(fake_client),
        source_events=SourceEventRepository(fake_client),
        documents=DocumentRepository(fake_client),
    )

    result1 = await svc.seed()
    result2 = await svc.seed()
    # Ambos devuelven lo mismo: no hay error por duplicado
    assert result1["commitment_id"] == result2["commitment_id"]
    assert result1["project_id"] == result2["project_id"]


@pytest.mark.asyncio
async def test_reset_cleans_only_demo(fake_client: FakeSupabaseClient):
    """Reset borra solo datos demo (los UUIDs fijos)."""
    from app.repositories.domain import (
        CommitmentRepository,
        DocumentRepository,
        ProjectRepository,
        SourceEventRepository,
    )

    fake_client.for_table("projects").returns([])
    fake_client.for_table("commitments").returns([])
    fake_client.for_table("source_events").returns([])
    fake_client.for_table("documents").returns([])

    svc = DemoService(
        projects=ProjectRepository(fake_client),
        commitments=CommitmentRepository(fake_client),
        source_events=SourceEventRepository(fake_client),
        documents=DocumentRepository(fake_client),
    )

    result = await svc.reset()
    assert result["status"] == "cleaned"
    assert result["commitment_id"] == str(DEMO_COMMITMENT_ID)


@pytest.mark.asyncio
async def test_simulate_returns_202(app_dev, fake_client: FakeSupabaseClient):
    """POST /demo/simulate responde 202 (accepted) y dispara background."""
    fake_client.for_table("projects").returns([FAKE_PROJECT_ROW])
    fake_client.for_table("commitments").returns([FAKE_COMMITMENT_ROW])
    fake_client.for_table("source_events").returns([{"id": str(DEMO_EVENT_IDS[0])}])
    fake_client.for_table("documents").returns([{"id": str(DEMO_DOCUMENT_IDS[0])}])
    fake_client.for_table("agent_runs").returns([{"id": "00000000-0000-4000-8000-000000000099"}])
    fake_client.for_table("risk_cases").returns([{"id": "00000000-0000-4000-8000-000000000098"}])
    fake_client.for_table("findings").returns([])
    fake_client.for_table("evidence").returns([])
    fake_client.for_table("alerts").returns([])
    fake_client.for_table("decisions").returns([])
    fake_client.for_table("timeline_events").returns([])
    async with client_for(app_dev) as client:
        resp = await client.post("/demo/simulate")
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_get_signals_returns_all_providers(fake_client: FakeSupabaseClient):
    """get_signals devuelve finance, jira, github, supabase."""
    from app.repositories.domain import (
        CommitmentRepository,
        DocumentRepository,
        ProjectRepository,
        SourceEventRepository,
    )

    svc = DemoService(
        projects=ProjectRepository(fake_client),
        commitments=CommitmentRepository(fake_client),
        source_events=SourceEventRepository(fake_client),
        documents=DocumentRepository(fake_client),
    )

    signals = await svc.get_signals()
    assert "finance" in signals
    assert "jira" in signals
    assert "github" in signals
    assert "supabase" in signals


# --- Test de reproducibilidad del caso demo -----------------------------------------


@pytest.mark.asyncio
async def test_demo_case_produces_critical_risk():
    """TEST DE REPRODUCIBILIDAD: el caso demo produce score >= 80 y severity critical.

    Este test ejecuta los agentes especializados sobre las señales del fixture y valida
    que el orquestador produce un RiskCase con la severidad esperada.
    """
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.agents.risk_orchestrator import RiskOrchestrator
    from app.agents.specialized import AgentContext
    from app.schemas.domain import CommitmentSnapshot, ProjectSnapshot, Severity
    from app.services.demo_service import _load_case

    case = _load_case()

    commitment = CommitmentSnapshot(
        id=DEMO_COMMITMENT_ID,
        project_id=DEMO_PROJECT_ID,
        title=case["commitment"]["title"],
        description=case["commitment"]["description"],
        beneficiary=case["commitment"]["beneficiary"],
        owner=case["commitment"]["owner"],
        due_date=datetime(2026, 7, 24, 23, 59, 59, tzinfo=UTC),
        financial_exposure=Decimal("20000"),
        currency="USD",
        priority="critical",
        status="at_risk",
        metadata=case["commitment"].get("metadata", {}),
    )

    project = ProjectSnapshot(
        id=DEMO_PROJECT_ID,
        name=case["project"]["name"],
        hourly_cost=Decimal(case["project"]["hourly_cost"]),
        currency="USD",
        external_references=case["project"]["external_references"],
    )

    context = AgentContext(
        commitment=commitment,
        project=project,
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),  # Un día después del due_date
        signals=case["signals"],
        recent_events=[],
        documents=[],
    )

    orchestrator = RiskOrchestrator()
    risk_case = orchestrator.analyze(context)

    # El caso DEBE producir score >= 80 y severidad CRITICAL
    assert risk_case.consolidated_score >= 80, (
        f"Score esperado >= 80, obtenido: {risk_case.consolidated_score}"
    )
    assert risk_case.severity == Severity.CRITICAL, (
        f"Severity esperada CRITICAL, obtenida: {risk_case.severity}"
    )


@pytest.mark.asyncio
async def test_demo_case_has_causal_chain():
    """El caso demo produce una cadena causal no vacía."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.agents.risk_orchestrator import RiskOrchestrator
    from app.agents.specialized import AgentContext
    from app.schemas.domain import CommitmentSnapshot, ProjectSnapshot
    from app.services.demo_service import _load_case

    case = _load_case()

    commitment = CommitmentSnapshot(
        id=DEMO_COMMITMENT_ID,
        project_id=DEMO_PROJECT_ID,
        title=case["commitment"]["title"],
        due_date=datetime(2026, 7, 24, 23, 59, 59, tzinfo=UTC),
        financial_exposure=Decimal("20000"),
        priority="critical",
        status="at_risk",
    )

    project = ProjectSnapshot(
        id=DEMO_PROJECT_ID,
        name=case["project"]["name"],
        hourly_cost=Decimal("75"),
        external_references=case["project"]["external_references"],
    )

    context = AgentContext(
        commitment=commitment,
        project=project,
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
        signals=case["signals"],
        recent_events=[],
        documents=[],
    )

    orchestrator = RiskOrchestrator()
    risk_case = orchestrator.analyze(context)
    assert len(risk_case.causal_chain) > 0


@pytest.mark.asyncio
async def test_demo_case_has_scenarios():
    """El caso demo produce los 3 escenarios obligatorios."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from app.agents.risk_orchestrator import RiskOrchestrator
    from app.agents.specialized import AgentContext
    from app.schemas.domain import CommitmentSnapshot, ProjectSnapshot
    from app.services.demo_service import _load_case

    case = _load_case()

    commitment = CommitmentSnapshot(
        id=DEMO_COMMITMENT_ID,
        project_id=DEMO_PROJECT_ID,
        title=case["commitment"]["title"],
        due_date=datetime(2026, 7, 24, 23, 59, 59, tzinfo=UTC),
        financial_exposure=Decimal("20000"),
        priority="critical",
        status="at_risk",
    )

    project = ProjectSnapshot(
        id=DEMO_PROJECT_ID,
        name=case["project"]["name"],
        hourly_cost=Decimal("75"),
        external_references=case["project"]["external_references"],
    )

    context = AgentContext(
        commitment=commitment,
        project=project,
        now=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
        signals=case["signals"],
        recent_events=[],
        documents=[],
    )

    orchestrator = RiskOrchestrator()
    risk_case = orchestrator.analyze(context)
    assert len(risk_case.scenarios) == 3
