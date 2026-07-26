"""Tests de los repositorios del dominio Datgent.

Se prueban contra el doble de Supabase, no contra una instancia real (RNF-4.2). Lo que
se afirma no es solo el valor devuelto, sino la consulta construida: es ahi donde se
detecta un filtro de borrado logico ausente o una restriccion de conflicto equivocada.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import DuplicateEventError, EntityNotFoundError
from app.repositories.base import UNIQUE_VIOLATION
from app.repositories.domain import (
    AgentRunRepository,
    AlertRepository,
    CommitmentRepository,
    DecisionRepository,
    DocumentRepository,
    EvidenceRepository,
    FindingRepository,
    ProjectRepository,
    ProviderConnectionRepository,
    RiskCaseRepository,
    SourceEventRepository,
    TimelineRepository,
)
from app.tests.fakes.supabase import FakeSupabaseClient

pytestmark = pytest.mark.anyio


class TestProjectRepository:
    async def test_reads_exclude_soft_deleted(self) -> None:
        """El filtro de borrado logico no queda a criterio de quien llama (RF-7.4)."""
        fake = FakeSupabaseClient()
        fake.for_table("projects").returns([{"id": str(uuid4()), "name": "Datgent"}])
        repo = ProjectRepository(fake)

        await repo.get(uuid4())

        assert fake.for_table("projects").called("is_")

    async def test_find_by_external_reference_filters_in_database(self) -> None:
        """El filtrado por JSONB ocurre en la base de datos, no en Python."""
        fake = FakeSupabaseClient()
        fake.for_table("projects").returns([{"id": str(uuid4()), "name": "Datgent"}])
        repo = ProjectRepository(fake)

        found = await repo.find_by_external_reference("jira", "DAT")

        assert found is not None
        contains_calls = fake.for_table("projects").calls_to("contains")
        assert contains_calls[0].args == ("external_references", {"jira": "DAT"})

    async def test_missing_project_returns_none(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("projects").returns([])
        repo = ProjectRepository(fake)

        assert await repo.get(uuid4()) is None


class TestCommitmentRepository:
    async def test_at_risk_orders_by_due_date_ascending(self) -> None:
        """De un compromiso en riesgo importa cuanto falta, no cuando se creo."""
        fake = FakeSupabaseClient()
        fake.for_table("commitments").returns([], count=0)
        repo = CommitmentRepository(fake)

        await repo.list_at_risk()

        order_call = fake.for_table("commitments").calls_to("order")[0]
        assert order_call.args == ("due_date",)
        assert order_call.kwargs == {"desc": False}

    async def test_set_status_updates_only_status(self) -> None:
        commitment_id = uuid4()
        fake = FakeSupabaseClient()
        fake.for_table("commitments").returns([{"id": str(commitment_id)}])
        repo = CommitmentRepository(fake)

        await repo.set_status(commitment_id, "at_risk")

        assert fake.for_table("commitments").payload() == {"status": "at_risk"}

    async def test_update_of_absent_row_raises_not_found(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("commitments").returns([])
        repo = CommitmentRepository(fake)

        with pytest.raises(EntityNotFoundError):
            await repo.set_status(uuid4(), "met")


class TestProviderConnectionRepository:
    async def test_upsert_uses_project_provider_conflict_target(self) -> None:
        """La unicidad es (project_id, provider): un provider por proyecto."""
        fake = FakeSupabaseClient()
        fake.for_table("provider_connections").returns([{"id": str(uuid4())}])
        repo = ProviderConnectionRepository(fake)

        await repo.upsert_status(provider="jira", project_id=uuid4(), status="connected")

        upsert_call = fake.for_table("provider_connections").calls_to("upsert")[0]
        assert upsert_call.kwargs["on_conflict"] == "project_id,provider"

    async def test_connected_status_stamps_last_sync(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("provider_connections").returns([{"id": str(uuid4())}])
        repo = ProviderConnectionRepository(fake)

        await repo.upsert_status(provider="github", project_id=None, status="connected")

        assert fake.for_table("provider_connections").payload()["last_sync_at"]

    async def test_error_status_does_not_stamp_last_sync(self) -> None:
        """Un fallo no es una sincronizacion: no debe marcar que hubo una."""
        fake = FakeSupabaseClient()
        fake.for_table("provider_connections").returns([{"id": str(uuid4())}])
        repo = ProviderConnectionRepository(fake)

        await repo.upsert_status(
            provider="github", project_id=None, status="error", last_error="401"
        )

        assert "last_sync_at" not in fake.for_table("provider_connections").payload()


class TestSourceEventRepository:
    async def test_duplicate_hash_is_translated_to_domain_error(self) -> None:
        """RF-6.4: la unicidad la impone la base de datos y se trata como duplicado."""
        fake = FakeSupabaseClient()
        fake.for_table("source_events").raises_api_error(UNIQUE_VIOLATION)
        repo = SourceEventRepository(fake)

        with pytest.raises(DuplicateEventError):
            await repo.create(
                {
                    "provider": "jira",
                    "external_id": "DAT-42",
                    "event_type": "issue_updated",
                    "event_hash": "abc",
                    "occurred_at": "2026-07-26T00:00:00Z",
                }
            )

    async def test_recent_events_come_newest_first(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("source_events").returns([])
        repo = SourceEventRepository(fake)

        await repo.list_recent_for_commitment(uuid4())

        order_call = fake.for_table("source_events").calls_to("order")[0]
        assert order_call.kwargs == {"desc": True}

    async def test_failure_reason_is_truncated(self) -> None:
        """Una traza completa no cabe ni tiene sentido en una columna de estado."""
        fake = FakeSupabaseClient()
        fake.for_table("source_events").returns([{"id": str(uuid4())}])
        repo = SourceEventRepository(fake)

        await repo.mark_failed(uuid4(), "x" * 2000)

        assert len(fake.for_table("source_events").payload()["processing_error"]) == 500

    async def test_pending_includes_failed_for_reconciliation(self) -> None:
        """La reconciliacion manual tiene que poder reintentar lo que fallo."""
        fake = FakeSupabaseClient()
        fake.for_table("source_events").returns([])
        repo = SourceEventRepository(fake)

        await repo.list_pending()

        in_call = fake.for_table("source_events").calls_to("in_")[0]
        assert in_call.args == ("processing_status", ["pending", "failed"])


class TestAgentRunRepository:
    async def test_run_is_opened_before_execution(self) -> None:
        """Si el agente muere sin devolver nada, la fila queda como rastro."""
        fake = FakeSupabaseClient()
        fake.for_table("agent_runs").returns([{"id": str(uuid4())}])
        repo = AgentRunRepository(fake)

        await repo.start(agent_name="jira-agent", commitment_id=uuid4(), model="gpt-4o-mini")

        payload = fake.for_table("agent_runs").payload()
        assert payload["status"] == "running"
        assert payload["started_at"]
        assert payload["model"] == "gpt-4o-mini"

    async def test_finish_records_output_and_duration(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("agent_runs").returns([{"id": str(uuid4())}])
        repo = AgentRunRepository(fake)

        await repo.finish(uuid4(), output={"risk_score": 70}, duration_ms=120)

        payload = fake.for_table("agent_runs").payload()
        assert payload["status"] == "completed"
        assert payload["output"] == {"risk_score": 70}
        assert payload["duration_ms"] == 120

    async def test_failure_records_error(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("agent_runs").returns([{"id": str(uuid4())}])
        repo = AgentRunRepository(fake)

        await repo.fail(uuid4(), "timeout del proveedor")

        payload = fake.for_table("agent_runs").payload()
        assert payload["status"] == "failed"
        assert payload["error"] == "timeout del proveedor"


class TestFindingAndEvidenceRepositories:
    async def test_findings_come_by_risk_descending(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("findings").returns([])
        repo = FindingRepository(fake)

        await repo.list_for_commitment(uuid4())

        order_call = fake.for_table("findings").calls_to("order")[0]
        assert order_call.args == ("risk_score",)
        assert order_call.kwargs == {"desc": True}

    async def test_evidence_batch_is_a_single_insert(self) -> None:
        """Una ida y vuelta por evidencia no escala: un analisis genera decenas."""
        fake = FakeSupabaseClient()
        fake.for_table("evidence").returns([{"id": str(uuid4())}, {"id": str(uuid4())}])
        repo = EvidenceRepository(fake)

        await repo.create_many(
            [
                {"finding_id": str(uuid4()), "provider": "jira", "source_type": "jira"},
                {"finding_id": str(uuid4()), "provider": "github", "source_type": "github"},
            ]
        )

        assert len(fake.for_table("evidence").calls_to("insert")) == 1

    async def test_empty_evidence_batch_does_not_touch_the_database(self) -> None:
        fake = FakeSupabaseClient()
        repo = EvidenceRepository(fake)

        assert await repo.create_many([]) == []
        assert fake.for_table("evidence").calls == []


class TestRiskCaseRepository:
    async def test_latest_returns_most_recent(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("risk_cases").returns([{"id": str(uuid4()), "consolidated_score": 80}])
        repo = RiskCaseRepository(fake)

        latest = await repo.latest_for_commitment(uuid4())

        assert latest is not None
        order_call = fake.for_table("risk_cases").calls_to("order")[0]
        assert order_call.kwargs == {"desc": True}
        assert fake.for_table("risk_cases").calls_to("limit")[0].args == (1,)

    async def test_no_case_yet_returns_none(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("risk_cases").returns([])
        repo = RiskCaseRepository(fake)

        assert await repo.latest_for_commitment(uuid4()) is None


class TestAlertRepository:
    async def test_acknowledge_records_who_and_when(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("alerts").returns([{"id": str(uuid4())}])
        repo = AlertRepository(fake)

        await repo.acknowledge(uuid4(), "ana@datgent.dev")

        payload = fake.for_table("alerts").payload()
        assert payload["status"] == "acknowledged"
        assert payload["acknowledged_by"] == "ana@datgent.dev"
        assert payload["acknowledged_at"]

    async def test_resolve_fills_acknowledged_at_to_satisfy_check(self) -> None:
        """La restriccion del esquema rechaza resolver sin haber reconocido."""
        fake = FakeSupabaseClient()
        fake.for_table("alerts").returns([{"id": str(uuid4())}])
        repo = AlertRepository(fake)

        await repo.resolve(uuid4())

        payload = fake.for_table("alerts").payload()
        assert payload["status"] == "resolved"
        assert payload["resolved_at"]
        assert payload["acknowledged_at"]


class TestDecisionRepository:
    async def test_approve_records_approver(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("decisions").returns([{"id": str(uuid4())}])
        repo = DecisionRepository(fake)

        await repo.approve(uuid4(), "cto@datgent.dev")

        payload = fake.for_table("decisions").payload()
        assert payload["approval_status"] == "approved"
        assert payload["approved_by"] == "cto@datgent.dev"
        assert payload["approved_at"]

    async def test_reject_requires_and_stores_reason(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("decisions").returns([{"id": str(uuid4())}])
        repo = DecisionRepository(fake)

        await repo.reject(uuid4(), "cto@datgent.dev", "el alcance no se renegocia")

        payload = fake.for_table("decisions").payload()
        assert payload["approval_status"] == "rejected"
        assert payload["rejection_reason"] == "el alcance no se renegocia"

    async def test_successful_execution_is_timestamped(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("decisions").returns([{"id": str(uuid4())}])
        repo = DecisionRepository(fake)

        await repo.mark_execution(uuid4(), status="succeeded", result={"issue": "DAT-42"})

        payload = fake.for_table("decisions").payload()
        assert payload["execution_status"] == "succeeded"
        assert payload["executed_at"]

    async def test_running_execution_is_not_timestamped_yet(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("decisions").returns([{"id": str(uuid4())}])
        repo = DecisionRepository(fake)

        await repo.mark_execution(uuid4(), status="running")

        assert "executed_at" not in fake.for_table("decisions").payload()


class TestTimelineRepository:
    async def test_append_records_actor_and_summary(self) -> None:
        commitment_id = uuid4()
        fake = FakeSupabaseClient()
        fake.for_table("timeline_events").returns([{"id": str(uuid4())}])
        repo = TimelineRepository(fake)

        await repo.append(
            commitment_id=commitment_id,
            actor_type="agent",
            actor_name="jira-agent",
            event_type="analysis.completed",
            summary="Issue bloqueado sin responsable",
        )

        payload = fake.for_table("timeline_events").payload()
        assert payload["commitment_id"] == str(commitment_id)
        assert payload["actor_type"] == "agent"
        assert payload["summary"] == "Issue bloqueado sin responsable"

    async def test_timeline_comes_newest_first(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("timeline_events").returns([])
        repo = TimelineRepository(fake)

        await repo.list_for_commitment(uuid4())

        assert fake.for_table("timeline_events").calls_to("order")[0].kwargs == {"desc": True}


class TestDocumentRepository:
    async def test_fulltext_search_filters_by_scope(self) -> None:
        project_id = uuid4()
        fake = FakeSupabaseClient()
        fake.for_table("documents").returns([{"id": str(uuid4()), "title": "SLA"}])
        repo = DocumentRepository(fake)

        rows = await repo.search_fulltext("penalizacion", project_id=project_id)

        assert rows
        ilike_call = fake.for_table("documents").calls_to("ilike")[0]
        assert ilike_call.args == ("content", "%penalizacion%")
        eq_columns = [call.args[0] for call in fake.for_table("documents").calls_to("eq")]
        assert "project_id" in eq_columns

    async def test_blank_query_does_not_touch_the_database(self) -> None:
        """Una consulta vacia haria un ``ilike '%%'`` que devuelve la tabla entera."""
        fake = FakeSupabaseClient()
        repo = DocumentRepository(fake)

        assert await repo.search_fulltext("   ") == []
        assert fake.for_table("documents").calls == []
