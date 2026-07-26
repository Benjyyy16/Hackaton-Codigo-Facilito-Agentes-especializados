"""Tests de la ingesta por webhook (RF-5, RF-6)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI

from app.api.deps import get_post_ingest_hook
from app.core.exceptions import WebhookAuthError
from app.integrations.jira.security import (
    WEBHOOK_SECRET_HEADER,
    secrets_match,
    verify_webhook_secret,
)
from app.repositories.base import UNIQUE_VIOLATION
from app.services.webhook_service import IngestOutcome, WebhookService
from app.tests.conftest import VALID_SETTINGS, client_for
from app.tests.fakes.supabase import FakeSupabaseClient

WEBHOOK_SECRET = VALID_SETTINGS["JIRA_WEBHOOK_SECRET"]
PROJECT_ROW = {"id": str(uuid4()), "jira_project_key": "DEMO", "name": "Demo"}


def _payload(event: str = "jira:issue_updated", issue_id: str = "10101") -> dict[str, Any]:
    return {
        "webhookEvent": event,
        "timestamp": 1785000000000,
        "issue": {
            "id": issue_id,
            "key": "DEMO-42",
            "fields": {
                "summary": "Entregar el informe",
                "status": {"name": "In Progress"},
                "duedate": "2026-08-15",
                "timeoriginalestimate": 28800,
                "updated": "2026-07-10T11:30:00.000+0000",
                "project": {"key": "DEMO"},
            },
        },
    }


def _arrange_new_event(fake: FakeSupabaseClient, event_id: str | None = None) -> str:
    """Prepara el doble para el camino de evento nuevo.

    Sobre ``jira_events`` ocurren dos ejecuciones seguidas con resultados distintos: la
    búsqueda por huella no encuentra nada, y la inserción devuelve la fila creada. De ahí la
    cola de respuestas.
    """
    identifier = event_id or str(uuid4())
    fake.for_table("projects").returns([PROJECT_ROW])
    fake.for_table("jira_events").then([]).then(
        [{"id": identifier, "project_id": PROJECT_ROW["id"]}]
    )
    return identifier


class TestSecretVerification:
    """RF-5.2 y RNF-1.3."""

    def test_matching_secret_passes(self, settings) -> None:
        verify_webhook_secret(
            settings.JIRA_WEBHOOK_SECRET, header_value=WEBHOOK_SECRET
        )

    def test_secret_accepted_from_query_parameter(self, settings) -> None:
        """Algunos formularios de webhook solo permiten configurar la URL."""
        verify_webhook_secret(settings.JIRA_WEBHOOK_SECRET, query_value=WEBHOOK_SECRET)

    @pytest.mark.parametrize("provided", [None, "", "incorrecto", WEBHOOK_SECRET[:-1]])
    def test_invalid_secret_is_rejected(self, settings, provided: str | None) -> None:
        with pytest.raises(WebhookAuthError):
            verify_webhook_secret(
                settings.JIRA_WEBHOOK_SECRET, header_value=provided
            )

    def test_comparison_is_constant_time(self) -> None:
        """``==`` cortocircuita y filtra cuántos caracteres coinciden."""
        import inspect

        from app.integrations.jira import security

        assert "compare_digest" in inspect.getsource(security.secrets_match)

    def test_secrets_match_rejects_empty(self, settings) -> None:
        assert secrets_match(None, settings.JIRA_WEBHOOK_SECRET) is False
        assert secrets_match("", settings.JIRA_WEBHOOK_SECRET) is False


class TestWebhookEndpointAuthorisation:
    async def test_missing_secret_returns_401(self, app: FastAPI) -> None:
        async with client_for(app) as client:
            response = await client.post("/webhooks/jira", json=_payload())

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "webhook_unauthorized"

    async def test_wrong_secret_returns_401(self, app: FastAPI) -> None:
        async with client_for(app) as client:
            response = await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: "no-es-el-secreto"},
            )

        assert response.status_code == 401

    async def test_unauthorised_payload_is_never_persisted(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-5.2: la validación va antes de cualquier escritura."""
        async with client_for(app) as client:
            await client.post("/webhooks/jira", json=_payload())

        assert fake_supabase.for_table("jira_events").calls == []
        assert fake_supabase.for_table("projects").calls == []

    async def test_secret_via_query_parameter_is_accepted(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        _arrange_new_event(fake_supabase)

        async with client_for(app) as client:
            response = await client.post(
                f"/webhooks/jira?secret={WEBHOOK_SECRET}", json=_payload()
            )

        assert response.status_code == 200

    async def test_error_body_does_not_reveal_the_secret(self, app: FastAPI) -> None:
        async with client_for(app) as client:
            response = await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: "intento"},
            )

        assert WEBHOOK_SECRET not in response.text


class TestWebhookEndpointIngestion:
    async def test_new_event_is_accepted(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-5.1."""
        event_id = _arrange_new_event(fake_supabase)

        async with client_for(app) as client:
            response = await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] is True
        assert body["duplicated"] is False
        assert body["event_id"] == event_id

    async def test_raw_payload_is_stored_verbatim(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-5.6."""
        _arrange_new_event(fake_supabase)
        payload = _payload()

        async with client_for(app) as client:
            await client.post(
                "/webhooks/jira",
                json=payload,
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        stored = fake_supabase.for_table("jira_events").payload()
        assert stored["raw_payload"] == payload

    async def test_fingerprint_is_persisted(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-6.1."""
        _arrange_new_event(fake_supabase)

        async with client_for(app) as client:
            await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        stored = fake_supabase.for_table("jira_events").payload()
        assert len(stored["fingerprint"]) == 64

    @pytest.mark.parametrize(
        "event",
        ["jira:issue_created", "jira:issue_updated", "comment_created"],
    )
    async def test_supported_event_types_are_accepted(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient, event: str
    ) -> None:
        """RF-5.3."""
        _arrange_new_event(fake_supabase)

        async with client_for(app) as client:
            response = await client.post(
                "/webhooks/jira",
                json=_payload(event),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert response.status_code == 200

    async def test_unsupported_event_returns_202(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-5.4: se descarta de forma explícita, no en silencio."""
        _arrange_new_event(fake_supabase)

        async with client_for(app) as client:
            response = await client.post(
                "/webhooks/jira",
                json=_payload("jira:worklog_updated"),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert response.status_code == 202
        assert response.json()["error"]["code"] == "unsupported_event"

    async def test_unsupported_event_is_not_persisted(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        async with client_for(app) as client:
            await client.post(
                "/webhooks/jira",
                json=_payload("jira:worklog_updated"),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert not fake_supabase.for_table("jira_events").called("insert")

    async def test_project_is_created_on_demand(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """La ingesta no debe fallar porque el proyecto no se diera de alta a mano."""
        _arrange_new_event(fake_supabase)

        async with client_for(app) as client:
            response = await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert response.status_code == 200
        assert fake_supabase.for_table("projects").called("select")


class TestBackgroundAnalysis:
    """RF-5.7 y RF-5.8."""

    async def test_analysis_is_scheduled_after_ingestion(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        _arrange_new_event(fake_supabase)
        scheduled: list[IngestOutcome] = []

        async def _capture(outcome: IngestOutcome) -> None:
            scheduled.append(outcome)

        app.dependency_overrides[get_post_ingest_hook] = lambda: _capture

        async with client_for(app) as client:
            await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert len(scheduled) == 1
        assert scheduled[0].event.jira_issue_key == "DEMO-42"

    async def test_failing_analysis_does_not_lose_the_event(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """El evento ya está persistido cuando el análisis se ejecuta."""
        _arrange_new_event(fake_supabase)

        async def _explode(_outcome: IngestOutcome) -> None:
            raise RuntimeError("el análisis falló")

        app.dependency_overrides[get_post_ingest_hook] = lambda: _explode

        async with client_for(app) as client:
            response = await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert response.status_code == 200
        assert fake_supabase.for_table("jira_events").called("insert")

    async def test_duplicate_does_not_schedule_analysis(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """Reanalizar un evento ya visto solo gastaría trabajo."""
        fake_supabase.for_table("jira_events").returns([{"id": str(uuid4())}])
        scheduled: list[IngestOutcome] = []

        async def _capture(outcome: IngestOutcome) -> None:
            scheduled.append(outcome)

        app.dependency_overrides[get_post_ingest_hook] = lambda: _capture

        async with client_for(app) as client:
            await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert scheduled == []

    async def test_default_hook_swallows_its_own_failures(self) -> None:
        """Una tarea de fondo que propaga no tiene a nadie que la recoja."""
        from app.api.deps import run_post_ingest
        from app.schemas.jira import EventType, NormalizedEvent

        event = NormalizedEvent(
            jira_issue_id="1",
            jira_issue_key="DEMO-1",
            project_key="DEMO",
            event_type=EventType.ISSUE_UPDATED,
            occurred_at="2026-07-10T11:30:00+00:00",  # type: ignore[arg-type]
            raw_payload={},
        )

        await run_post_ingest(IngestOutcome(event=event, row=None, duplicated=False))


class TestDeduplication:
    """RF-6."""

    async def test_known_fingerprint_is_reported_as_duplicate(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-5.5."""
        existing_id = str(uuid4())
        fake_supabase.for_table("jira_events").returns([{"id": existing_id}])

        async with client_for(app) as client:
            response = await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["duplicated"] is True
        assert body["event_id"] == existing_id

    async def test_duplicate_is_not_inserted_again(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-6.2."""
        fake_supabase.for_table("jira_events").returns([{"id": str(uuid4())}])

        async with client_for(app) as client:
            await client.post(
                "/webhooks/jira",
                json=_payload(),
                headers={WEBHOOK_SECRET_HEADER: WEBHOOK_SECRET},
            )

        assert not fake_supabase.for_table("jira_events").called("insert")

    async def test_unique_violation_is_treated_as_duplicate(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-6.4: cubre la carrera entre la comprobación previa y la inserción.

        Se ejercita el servicio directamente, porque el escenario requiere que la lectura
        devuelva vacío y la escritura falle, dos respuestas distintas para la misma tabla.
        """
        from app.integrations.jira.normalizer import normalize_webhook_payload
        from app.repositories.jira_events import JiraEventRepository
        from app.repositories.projects import ProjectRepository

        class RacingEvents(JiraEventRepository):
            def __init__(self) -> None:
                super().__init__(fake_supabase)
                self.lookups = 0

            async def get_by_fingerprint(self, fingerprint: str):  # type: ignore[override]
                self.lookups += 1
                # Primera lectura: no existe. Segunda, tras la violación: ya está.
                return None if self.lookups == 1 else {"id": "ganador"}

            async def create(self, payload):  # type: ignore[override]
                fake_supabase.for_table("jira_events").raises_api_error(UNIQUE_VIOLATION)
                return await super().create(payload)

        fake_supabase.for_table("projects").returns([PROJECT_ROW])
        events = RacingEvents()
        service = WebhookService(ProjectRepository(fake_supabase), events)

        outcome = await service.ingest_event(normalize_webhook_payload(_payload()))

        assert outcome.duplicated is True
        assert outcome.row == {"id": "ganador"}
        assert events.lookups == 2

    async def test_different_events_are_not_confused(
        self, fake_supabase: FakeSupabaseClient
    ) -> None:
        from app.integrations.jira.normalizer import normalize_webhook_payload

        first = normalize_webhook_payload(_payload(issue_id="1"))
        second = normalize_webhook_payload(_payload(issue_id="2"))

        assert first.fingerprint != second.fingerprint


class TestOpenApiDocumentation:
    """RNF-4.4."""

    def test_webhook_endpoint_is_documented(self, app: FastAPI) -> None:
        schema = app.openapi()

        operation = schema["paths"]["/webhooks/jira"]["post"]
        assert set(operation["responses"]) >= {"200", "202", "401", "422"}
