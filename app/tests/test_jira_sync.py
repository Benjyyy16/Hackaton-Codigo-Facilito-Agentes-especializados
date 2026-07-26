"""Tests de la sincronización inicial por JQL (RF-4)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import get_jira_sync_service
from app.core.exceptions import JiraNotFoundError, SupabaseError
from app.integrations.jira.client import JiraClient
from app.repositories.jira_events import JiraEventRepository
from app.repositories.projects import ProjectRepository
from app.services.jira_sync_service import JiraSyncService, build_project_jql
from app.services.webhook_service import IngestOutcome, WebhookService
from app.tests.conftest import client_for
from app.tests.fakes.supabase import FakeSupabaseClient

PROJECT_ROW = {"id": str(uuid4()), "jira_project_key": "DEMO", "name": "Demo"}


def _issue(key: str, issue_id: str, updated: str = "2026-07-10T11:30:00.000+0000") -> dict[str, Any]:
    return {
        "id": issue_id,
        "key": key,
        "fields": {
            "summary": f"Tarea {key}",
            "updated": updated,
            "duedate": "2026-08-15",
            "timeoriginalestimate": 3600,
            "project": {"key": "DEMO"},
        },
    }


class StubJiraClient:
    """Cliente de Jira sustituido, para probar el servicio sin la capa HTTP."""

    def __init__(
        self, issues: list[dict[str, Any]], *, project_exists: bool = True
    ) -> None:
        self._issues = issues
        self._project_exists = project_exists
        self.requested_jql: str | None = None
        self.requested_max: int | None = None

    async def get_project(self, project_key: str) -> dict[str, Any]:
        if not self._project_exists:
            raise JiraNotFoundError(details={"project": project_key})
        return {"key": project_key, "name": "Demo"}

    async def iter_issues(
        self, jql: str, *, max_issues: int | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        self.requested_jql = jql
        self.requested_max = max_issues
        emitted = 0
        for issue in self._issues:
            yield issue
            emitted += 1
            if max_issues is not None and emitted >= max_issues:
                return


def _service(
    fake: FakeSupabaseClient, issues: list[dict[str, Any]], **kwargs: Any
) -> tuple[JiraSyncService, StubJiraClient]:
    jira = StubJiraClient(issues, **kwargs)
    webhooks = WebhookService(ProjectRepository(fake), JiraEventRepository(fake))
    return JiraSyncService(jira, webhooks), jira  # type: ignore[arg-type]


def _arrange_new_events(fake: FakeSupabaseClient, count: int) -> None:
    """Cada issue produce una búsqueda por huella vacía y una inserción."""
    fake.for_table("projects").returns([PROJECT_ROW])
    table = fake.for_table("jira_events")
    for index in range(count):
        table.then([]).then([{"id": str(uuid4()), "project_id": PROJECT_ROW["id"]}])
        del index


class TestJqlConstruction:
    """RF-4.2."""

    def test_default_jql_targets_the_project(self) -> None:
        assert build_project_jql("DEMO").startswith('project = "DEMO"')

    def test_default_jql_orders_by_recency(self) -> None:
        """Si la recogida se corta, lo traído debe ser lo más reciente."""
        assert "ORDER BY updated DESC" in build_project_jql("DEMO")

    def test_quotes_in_the_key_are_escaped(self) -> None:
        """Un valor inesperado no debe poder alterar la estructura de la consulta."""
        result = build_project_jql('DE"MO')

        assert result == 'project = "DE\\"MO" ORDER BY updated DESC'

    async def test_custom_jql_is_used_verbatim(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-4.1."""
        _arrange_new_events(fake_supabase, 0)
        service, jira = _service(fake_supabase, [])

        result = await service.sync_project("DEMO", jql="assignee = currentUser()")

        assert jira.requested_jql == "assignee = currentUser()"
        assert result.jql == "assignee = currentUser()"

    async def test_default_jql_is_used_when_absent(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        service, jira = _service(fake_supabase, [])

        await service.sync_project("DEMO")

        assert jira.requested_jql == build_project_jql("DEMO")


class TestSyncCounts:
    """RF-4.5."""

    async def test_new_issues_are_counted_as_created(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        issues = [_issue("DEMO-1", "1"), _issue("DEMO-2", "2")]
        _arrange_new_events(fake_supabase, len(issues))
        service, _ = _service(fake_supabase, issues)

        result = await service.sync_project("DEMO")

        assert result.processed == 2
        assert result.created == 2
        assert result.skipped == 0
        assert result.failed == 0

    async def test_known_issues_are_counted_as_skipped(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-4.7: repetir la sincronización no crea eventos nuevos."""
        issues = [_issue("DEMO-1", "1"), _issue("DEMO-2", "2")]
        fake_supabase.for_table("projects").returns([PROJECT_ROW])
        # Toda búsqueda por huella encuentra el evento: ya se sincronizó antes.
        fake_supabase.for_table("jira_events").returns([{"id": str(uuid4())}])
        service, _ = _service(fake_supabase, issues)

        result = await service.sync_project("DEMO")

        assert result.processed == 2
        assert result.created == 0
        assert result.skipped == 2
        assert not fake_supabase.for_table("jira_events").called("insert")

    async def test_empty_project_reports_zero(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        service, _ = _service(fake_supabase, [])

        result = await service.sync_project("DEMO")

        assert result.processed == 0
        assert result.created == 0

    async def test_result_reports_the_project(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        service, _ = _service(fake_supabase, [])

        result = await service.sync_project("DEMO")

        assert result.project_key == "DEMO"


class TestPartialFailures:
    async def test_broken_issue_does_not_abort_the_sync(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        """Abortar dejaría el proyecto a medio cargar por un solo registro defectuoso."""
        issues = [
            _issue("DEMO-1", "1"),
            {"id": "2"},  # sin clave: el normalizador lo rechaza
            _issue("DEMO-3", "3"),
        ]
        _arrange_new_events(fake_supabase, 2)
        service, _ = _service(fake_supabase, issues)

        result = await service.sync_project("DEMO")

        assert result.processed == 3
        assert result.created == 2
        assert result.failed == 1

    async def test_storage_failure_on_one_issue_is_counted(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        issues = [_issue("DEMO-1", "1"), _issue("DEMO-2", "2")]
        fake_supabase.for_table("projects").returns([PROJECT_ROW])
        table = fake_supabase.for_table("jira_events")
        table.then([]).then([{"id": str(uuid4())}])  # primer issue bien
        table.then([]).then_raises(SupabaseError())  # segundo falla al insertar
        service, _ = _service(fake_supabase, issues)

        result = await service.sync_project("DEMO")

        assert result.created == 1
        assert result.failed == 1


class TestMissingProject:
    """RF-4.6."""

    async def test_unknown_project_raises_not_found(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        service, _ = _service(fake_supabase, [], project_exists=False)

        with pytest.raises(JiraNotFoundError):
            await service.sync_project("NOPE")

    async def test_existence_is_checked_before_iterating(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        """Una clave equivocada debe dar 404, no una sincronización vacía silenciosa."""
        service, jira = _service(
            fake_supabase, [_issue("DEMO-1", "1")], project_exists=False
        )

        with pytest.raises(JiraNotFoundError):
            await service.sync_project("NOPE")

        assert jira.requested_jql is None


class TestLimits:
    async def test_max_issues_is_forwarded_and_marks_truncation(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        issues = [_issue(f"DEMO-{n}", str(n)) for n in range(5)]
        _arrange_new_events(fake_supabase, 2)
        service, jira = _service(fake_supabase, issues)

        result = await service.sync_project("DEMO", max_issues=2)

        assert jira.requested_max == 2
        assert result.processed == 2
        assert result.truncated is True

    async def test_unlimited_sync_is_not_marked_truncated(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        issues = [_issue("DEMO-1", "1")]
        _arrange_new_events(fake_supabase, 1)
        service, _ = _service(fake_supabase, issues)

        result = await service.sync_project("DEMO")

        assert result.truncated is False


class TestSyncEndpoint:
    async def test_sync_returns_the_result(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        issues = [_issue("DEMO-1", "1")]
        _arrange_new_events(fake_supabase, 1)
        service, _ = _service(fake_supabase, issues)
        app.dependency_overrides[get_jira_sync_service] = lambda: service

        async with client_for(app) as client:
            response = await client.post("/jira/sync", json={"project_key": "DEMO"})

        assert response.status_code == 200
        body = response.json()
        assert body["project_key"] == "DEMO"
        assert body["created"] == 1

    async def test_unknown_project_returns_404(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        service, _ = _service(fake_supabase, [], project_exists=False)
        app.dependency_overrides[get_jira_sync_service] = lambda: service

        async with client_for(app) as client:
            response = await client.post("/jira/sync", json={"project_key": "NOPE"})

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "jira_not_found"

    async def test_missing_project_key_returns_422(self, app: FastAPI) -> None:
        async with client_for(app) as client:
            response = await client.post("/jira/sync", json={})

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    async def test_empty_project_key_returns_422(self, app: FastAPI) -> None:
        async with client_for(app) as client:
            response = await client.post("/jira/sync", json={"project_key": ""})

        assert response.status_code == 422

    async def test_out_of_range_max_issues_returns_422(self, app: FastAPI) -> None:
        async with client_for(app) as client:
            response = await client.post(
                "/jira/sync", json={"project_key": "DEMO", "max_issues": 0}
            )

        assert response.status_code == 422

    async def test_jira_unavailable_returns_502(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """El fallo de un sistema externo no debe presentarse como error propio."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        http = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.atlassian.net",
        )
        webhooks = WebhookService(
            ProjectRepository(fake_supabase), JiraEventRepository(fake_supabase)
        )
        service = JiraSyncService(JiraClient(http, max_retries=0), webhooks)
        app.dependency_overrides[get_jira_sync_service] = lambda: service

        async with client_for(app) as client:
            response = await client.post("/jira/sync", json={"project_key": "DEMO"})

        assert response.status_code == 502
        await http.aclose()

    def test_endpoint_is_documented(self, app: FastAPI) -> None:
        """RNF-4.4."""
        operation = app.openapi()["paths"]["/jira/sync"]["post"]

        assert set(operation["responses"]) >= {"200", "404", "422", "502"}


class TestNoPolling:
    """RF-12.7: la sincronización es a demanda, no un sondeo periódico."""

    def test_no_scheduler_or_polling_loop_exists(self) -> None:
        import inspect

        from app.services import jira_sync_service

        source = inspect.getsource(jira_sync_service)
        for forbidden in ("while True", "sleep", "schedule", "interval"):
            assert forbidden not in source


class TestIngestOutcome:
    def test_identifiers_are_parsed_from_the_row(self) -> None:
        from app.integrations.jira.normalizer import normalize_issue

        event = normalize_issue(_issue("DEMO-1", "1"))
        event_id = uuid4()
        outcome = IngestOutcome(
            event=event,
            row={"id": str(event_id), "project_id": PROJECT_ROW["id"]},
            duplicated=False,
        )

        assert outcome.event_id == event_id
        assert str(outcome.project_id) == PROJECT_ROW["id"]

    def test_absent_row_yields_no_identifiers(self) -> None:
        from app.integrations.jira.normalizer import normalize_issue

        outcome = IngestOutcome(
            event=normalize_issue(_issue("DEMO-1", "1")), row=None, duplicated=False
        )

        assert outcome.event_id is None
        assert outcome.project_id is None
