"""Tests de la capa de repositorios (RF-6, RF-7)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.exceptions import (
    DuplicateEventError,
    EntityNotFoundError,
    InvalidRequestError,
    SupabaseError,
)
from app.repositories.alerts import AlertRepository
from app.repositories.base import (
    FOREIGN_KEY_VIOLATION,
    MAX_PAGE_SIZE,
    UNIQUE_VIOLATION,
    BaseRepository,
    Page,
)
from app.repositories.commitments import CommitmentRepository
from app.repositories.events import EventRepository
from app.repositories.workspaces import WorkspaceRepository
from app.repositories.risk_analyses import RiskAnalysisRepository
from app.schemas.events import ProviderName
from app.tests.fakes.supabase import FakeSupabaseClient


@pytest.fixture
def client() -> FakeSupabaseClient:
    return FakeSupabaseClient()


class TestSoftDeleteFiltering:
    """RF-7.4: el filtro de borrado lógico no queda a criterio de quien llama."""

    async def test_read_on_soft_delete_table_excludes_deleted(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("workspaces").returns([{"id": str(uuid4())}])
        repo = WorkspaceRepository(client)

        await repo.get(uuid4())

        deleted_filters = client.for_table("workspaces").calls_to("is_")
        assert any(call.args == ("deleted_at", "null") for call in deleted_filters)

    async def test_read_on_history_table_does_not_filter(
        self, client: FakeSupabaseClient
    ) -> None:
        """Los eventos son un histórico: no hay borrado lógico que filtrar."""
        client.for_table("external_events").returns([{"id": str(uuid4())}])
        repo = EventRepository(client)

        await repo.get(uuid4())

        assert not client.for_table("external_events").called("is_")

    async def test_listing_applies_soft_delete_filter(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("alerts").returns([], count=0)
        repo = AlertRepository(client)

        await repo.list_alerts()

        assert client.for_table("alerts").called("is_")

    async def test_soft_delete_sets_timestamp(self, client: FakeSupabaseClient) -> None:
        entity_id = uuid4()
        client.for_table("workspaces").returns([{"id": str(entity_id)}])
        repo = WorkspaceRepository(client)

        await repo.soft_delete_by_id(entity_id)

        assert client.for_table("workspaces").payload()["deleted_at"] is not None

    async def test_soft_delete_rejected_on_history_table(
        self, client: FakeSupabaseClient
    ) -> None:
        repo = EventRepository(client)

        with pytest.raises(SupabaseError):
            await repo.soft_delete_by_id(uuid4())


class TestErrorTranslation:
    """RF-7.5 y RF-6.4: los errores de postgrest se traducen al dominio."""

    async def test_unique_violation_becomes_duplicate_event(
        self, client: FakeSupabaseClient
    ) -> None:
        """El caso que sostiene la deduplicación: duplicado, no fallo."""
        client.for_table("external_events").raises_api_error(UNIQUE_VIOLATION)
        repo = EventRepository(client)

        with pytest.raises(DuplicateEventError):
            await repo.create({"fingerprint": "abc"})

    async def test_foreign_key_violation_becomes_not_found(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("commitments").raises_api_error(FOREIGN_KEY_VIOLATION)
        repo = CommitmentRepository(client)

        with pytest.raises(EntityNotFoundError):
            await repo.create({"project_id": str(uuid4())})

    async def test_unknown_api_error_becomes_supabase_error(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("workspaces").raises_api_error("42P01", "tabla inexistente")
        repo = WorkspaceRepository(client)

        with pytest.raises(SupabaseError):
            await repo.create({"name": "x"})

    async def test_unexpected_exception_becomes_supabase_error(
        self, client: FakeSupabaseClient
    ) -> None:
        """Un fallo de red no debe escapar como excepción de librería."""
        client.for_table("workspaces").raises(ConnectionError("sin ruta al host"))
        repo = WorkspaceRepository(client)

        with pytest.raises(SupabaseError):
            await repo.get(uuid4())

    async def test_domain_error_does_not_leak_library_detail(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("workspaces").raises(ConnectionError("postgres://user:pw@host"))
        repo = WorkspaceRepository(client)

        with pytest.raises(SupabaseError) as excinfo:
            await repo.get(uuid4())

        assert "postgres://" not in str(excinfo.value)


class TestPagination:
    async def test_range_is_inclusive_on_both_ends(
        self, client: FakeSupabaseClient
    ) -> None:
        """``range`` de postgrest incluye ambos extremos: 20 filas son 0..19."""
        client.for_table("external_events").returns([], count=0)
        repo = EventRepository(client)

        await repo.list_events(limit=20, offset=0)

        assert client.for_table("external_events").calls_to("range")[0].args == (0, 19)

    async def test_offset_shifts_the_range(self, client: FakeSupabaseClient) -> None:
        client.for_table("external_events").returns([], count=0)
        repo = EventRepository(client)

        await repo.list_events(limit=10, offset=30)

        assert client.for_table("external_events").calls_to("range")[0].args == (30, 39)

    async def test_page_size_is_capped(self, client: FakeSupabaseClient) -> None:
        """Un cliente no puede pedir un rango arbitrariamente grande."""
        client.for_table("external_events").returns([], count=0)
        repo = EventRepository(client)

        await repo.list_events(limit=10_000)

        start, end = client.for_table("external_events").calls_to("range")[0].args
        assert end - start + 1 == MAX_PAGE_SIZE

    async def test_negative_offset_is_clamped(self, client: FakeSupabaseClient) -> None:
        client.for_table("external_events").returns([], count=0)
        repo = EventRepository(client)

        await repo.list_events(offset=-5)

        assert client.for_table("external_events").calls_to("range")[0].args[0] == 0

    async def test_exact_count_is_requested(self, client: FakeSupabaseClient) -> None:
        client.for_table("external_events").returns([], count=0)
        repo = EventRepository(client)

        await repo.list_events()

        select_call = client.for_table("external_events").calls_to("select")[0]
        assert select_call.kwargs.get("count") == "exact"

    async def test_total_comes_from_count(self, client: FakeSupabaseClient) -> None:
        client.for_table("external_events").returns([{"id": "1"}, {"id": "2"}], count=57)
        repo = EventRepository(client)

        page = await repo.list_events(limit=2)

        assert page.total == 57
        assert len(page.items) == 2
        assert page.has_more is True

    async def test_has_more_is_false_on_last_page(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("external_events").returns([{"id": "1"}], count=3)
        repo = EventRepository(client)

        page = await repo.list_events(limit=1, offset=2)

        assert page.has_more is False

    async def test_total_falls_back_to_row_count(
        self, client: FakeSupabaseClient
    ) -> None:
        """Si PostgREST no devuelve recuento, el total no puede quedar en ``None``."""
        client.for_table("external_events").returns([{"id": "1"}], count=None)
        repo = EventRepository(client)

        page = await repo.list_events()

        assert page.total == 1

    async def test_events_are_ordered_by_occurrence_descending(
        self, client: FakeSupabaseClient
    ) -> None:
        """RF-10.1: del más reciente al más antiguo."""
        client.for_table("external_events").returns([], count=0)
        repo = EventRepository(client)

        await repo.list_events()

        order_call = client.for_table("external_events").calls_to("order")[0]
        assert order_call.args[0] == "occurred_at"
        assert order_call.kwargs["desc"] is True


class TestFilters:
    async def test_none_filters_are_ignored(self, client: FakeSupabaseClient) -> None:
        """Permite que las rutas pasen sus parámetros opcionales tal cual."""
        client.for_table("alerts").returns([], count=0)
        repo = AlertRepository(client)

        await repo.list_alerts(severity=None, status=None)

        equality_columns = [
            call.args[0] for call in client.for_table("alerts").calls_to("eq")
        ]
        assert "severity" not in equality_columns
        assert "status" not in equality_columns

    async def test_provided_filters_are_applied(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("alerts").returns([], count=0)
        repo = AlertRepository(client)

        await repo.list_alerts(severity="critical", status="open")

        applied = {
            call.args[0]: call.args[1]
            for call in client.for_table("alerts").calls_to("eq")
        }
        assert applied == {"severity": "critical", "status": "open"}


class TestWriteContract:
    async def test_insert_without_returned_row_is_an_error(
        self, client: FakeSupabaseClient
    ) -> None:
        """Sin fila devuelta, la escritura no se puede considerar confirmada."""
        client.for_table("workspaces").returns([])
        repo = WorkspaceRepository(client)

        with pytest.raises(SupabaseError):
            await repo.create({"name": "x"})

    async def test_update_of_missing_row_is_not_found(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("workspaces").returns([])
        repo = WorkspaceRepository(client)

        with pytest.raises(EntityNotFoundError):
            await repo.update(uuid4(), {"name": "x"})

    async def test_update_does_not_send_updated_at(
        self, client: FakeSupabaseClient
    ) -> None:
        """``updated_at`` lo mantiene un trigger; enviarlo sería redundante."""
        client.for_table("workspaces").returns([{"id": str(uuid4())}])
        repo = WorkspaceRepository(client)

        await repo.update(uuid4(), {"name": "nuevo"})

        assert "updated_at" not in client.for_table("workspaces").payload()

    async def test_get_or_raise_reports_missing_entity(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("workspaces").returns([])
        repo = WorkspaceRepository(client)

        with pytest.raises(EntityNotFoundError):
            await repo.get_or_raise(uuid4())


class TestWorkspaceRepository:
    async def test_ensure_returns_existing_without_writing(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("workspaces").returns([{"id": str(uuid4()), "name": "Demo"}])
        repo = WorkspaceRepository(client)

        await repo.ensure(provider=ProviderName.JIRA, workspace_key="DEMO")

        assert not client.for_table("workspaces").called("upsert")

    async def test_missing_project_raises_with_key_in_details(
        self, client: FakeSupabaseClient
    ) -> None:
        """RF-4.6: proyecto inexistente se traduce a 404 aguas arriba."""
        client.for_table("workspaces").returns([])
        repo = WorkspaceRepository(client)

        with pytest.raises(EntityNotFoundError) as excinfo:
            await repo.get_by_key_or_raise(ProviderName.JIRA, "NOPE")

        assert excinfo.value.details == {"provider": "jira", "workspace_key": "NOPE"}


class TestEventRepository:
    async def test_fingerprint_lookup_filters_by_fingerprint(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("external_events").returns([{"id": str(uuid4())}])
        repo = EventRepository(client)

        found = await repo.get_by_fingerprint("abc123")

        assert found is not None
        applied = {
            call.args[0]: call.args[1]
            for call in client.for_table("external_events").calls_to("eq")
        }
        assert applied == {"fingerprint": "abc123"}

    async def test_unknown_fingerprint_returns_none(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("external_events").returns([])
        repo = EventRepository(client)

        assert await repo.get_by_fingerprint("nope") is None


class TestCommitmentRepository:
    async def test_upsert_targets_the_composite_constraint(
        self, client: FakeSupabaseClient
    ) -> None:
        """Reprocesar el mismo issue debe actualizar, no duplicar."""
        client.for_table("commitments").returns([{"id": str(uuid4())}])
        repo = CommitmentRepository(client)

        await repo.upsert_from_issue(
            workspace_id=uuid4(),
            provider="jira",
            external_key="DEMO-1",
            title="Entrega",
        )

        upsert_call = client.for_table("commitments").calls_to("upsert")[0]
        assert upsert_call.kwargs["on_conflict"] == "workspace_id,external_key"

    async def test_absent_optional_fields_are_not_written(
        self, client: FakeSupabaseClient
    ) -> None:
        """Un payload sin fecha no debe borrar la fecha ya registrada."""
        client.for_table("commitments").returns([{"id": str(uuid4())}])
        repo = CommitmentRepository(client)

        await repo.upsert_from_issue(
            workspace_id=uuid4(),
            provider="jira",
            external_key="DEMO-1",
            title="Entrega",
        )

        payload = client.for_table("commitments").payload()
        assert "due_date" not in payload
        assert "estimated_hours" not in payload

    async def test_provided_optional_fields_are_written(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("commitments").returns([{"id": str(uuid4())}])
        repo = CommitmentRepository(client)

        await repo.upsert_from_issue(
            workspace_id=uuid4(),
            provider="jira",
            external_key="DEMO-1",
            title="Entrega",
            due_date="2026-08-01T00:00:00+00:00",
            estimated_hours=12.5,
        )

        payload = client.for_table("commitments").payload()
        assert payload["due_date"] == "2026-08-01T00:00:00+00:00"
        assert payload["estimated_hours"] == 12.5


class TestRiskAnalysisRepository:
    async def test_analysis_without_target_is_rejected(
        self, client: FakeSupabaseClient
    ) -> None:
        """El esquema lo exige; fallar aquí da un error del dominio, no del motor."""
        repo = RiskAnalysisRepository(client)

        with pytest.raises(InvalidRequestError):
            await repo.record(risk_score=50, severity="medium", findings={})

    async def test_partial_flag_is_persisted(self, client: FakeSupabaseClient) -> None:
        """RF-8.6: un análisis con un agente caído queda marcado."""
        client.for_table("risk_analyses").returns([{"id": str(uuid4())}])
        repo = RiskAnalysisRepository(client)

        await repo.record(
            risk_score=80,
            severity="critical",
            findings={"technical": {}},
            event_id=uuid4(),
            is_partial=True,
        )

        assert client.for_table("risk_analyses").payload()["is_partial"] is True

    async def test_latest_for_commitment_orders_descending(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("risk_analyses").returns([{"id": str(uuid4())}], count=1)
        repo = RiskAnalysisRepository(client)

        await repo.get_latest_for_commitment(uuid4())

        order_call = client.for_table("risk_analyses").calls_to("order")[0]
        assert order_call.kwargs["desc"] is True


class TestAlertRepository:
    async def test_find_open_filters_by_commitment_reason_and_status(
        self, client: FakeSupabaseClient
    ) -> None:
        """RF-9.3: es la consulta que evita duplicar alertas."""
        client.for_table("alerts").returns([{"id": str(uuid4())}])
        repo = AlertRepository(client)

        await repo.find_open(uuid4(), "vencimiento superado")

        applied = {
            call.args[0] for call in client.for_table("alerts").calls_to("eq")
        }
        assert applied == {"commitment_id", "reason", "status"}

    async def test_resolving_sets_status_and_timestamp_together(
        self, client: FakeSupabaseClient
    ) -> None:
        """El esquema exige que una alerta resuelta tenga fecha de resolución."""
        client.for_table("alerts").returns([{"id": str(uuid4())}])
        repo = AlertRepository(client)

        await repo.resolve(uuid4())

        payload = client.for_table("alerts").payload()
        assert payload["status"] == "resolved"
        assert payload["resolved_at"] is not None

    async def test_open_alert_has_no_resolution_timestamp(
        self, client: FakeSupabaseClient
    ) -> None:
        client.for_table("alerts").returns([{"id": str(uuid4())}])
        repo = AlertRepository(client)

        await repo.open_alert(
            risk_analysis_id=uuid4(),
            severity="high",
            reason="vencimiento próximo",
            financial_impact=1250.0,
            commitment_id=uuid4(),
        )

        payload = client.for_table("alerts").payload()
        assert payload["status"] == "open"
        assert payload["resolved_at"] is None


class TestLayeringDiscipline:
    """RF-7.1 y RF-7.2: los repositorios son la única puerta a los datos."""

    def test_every_entity_has_its_own_repository(self) -> None:
        repositories = {
            WorkspaceRepository,
            EventRepository,
            CommitmentRepository,
            RiskAnalysisRepository,
            AlertRepository,
        }
        tables = {repo.table_name for repo in repositories}

        assert tables == {
            "workspaces",
            "external_events",
            "commitments",
            "risk_analyses",
            "alerts",
        }
        assert all(issubclass(repo, BaseRepository) for repo in repositories)

    def test_page_is_generic_over_rows(self) -> None:
        page: Page[dict[str, str]] = Page([{"a": "b"}], 1, limit=10, offset=0)
        assert page.items == [{"a": "b"}]
        assert page.has_more is False
