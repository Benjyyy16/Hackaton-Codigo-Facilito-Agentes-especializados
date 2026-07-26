"""Tests del normalizador de Jira (RF-4.4, RF-5.3, RF-5.4, RF-5.6, RF-6.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.exceptions import UnsupportedEventError
from app.integrations.jira.normalizer import (
    normalize_issue,
    normalize_webhook_payload,
    parse_jira_datetime,
    seconds_to_hours,
)
from app.schemas.jira import EventType


def _issue_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "summary": "Entregar el informe",
        "status": {"name": "In Progress"},
        "assignee": {"displayName": "Ada Lovelace"},
        "priority": {"name": "High"},
        "duedate": "2026-08-15",
        "timeoriginalestimate": 28800,  # 8 horas en segundos
        "labels": ["backend", "critico"],
        "created": "2026-07-01T09:00:00.000+0000",
        "updated": "2026-07-10T11:30:00.000+0000",
        "project": {"key": "DEMO", "name": "Demo"},
    }
    fields.update(overrides)
    return fields


def _webhook(event: str = "jira:issue_updated", **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "webhookEvent": event,
        "timestamp": 1785000000000,
        "issue": {"id": "10101", "key": "DEMO-42", "fields": _issue_fields()},
    }
    payload.update(extra)
    return payload


class TestSupportedEvents:
    """RF-5.3."""

    @pytest.mark.parametrize(
        ("webhook_event", "expected"),
        [
            ("jira:issue_created", EventType.ISSUE_CREATED),
            ("jira:issue_updated", EventType.ISSUE_UPDATED),
            ("comment_created", EventType.COMMENT_CREATED),
            ("jira:comment_created", EventType.COMMENT_CREATED),
        ],
    )
    def test_event_types_are_mapped(
        self, webhook_event: str, expected: EventType
    ) -> None:
        result = normalize_webhook_payload(_webhook(webhook_event))

        assert result.event_type is expected


class TestUnsupportedEvents:
    """RF-5.4: lo no soportado se descarta de forma explícita."""

    def test_unknown_event_is_rejected(self) -> None:
        with pytest.raises(UnsupportedEventError):
            normalize_webhook_payload(_webhook("jira:worklog_updated"))

    def test_payload_without_event_is_rejected(self) -> None:
        with pytest.raises(UnsupportedEventError):
            normalize_webhook_payload({"issue": {"key": "DEMO-1"}})

    def test_payload_without_issue_is_rejected(self) -> None:
        with pytest.raises(UnsupportedEventError):
            normalize_webhook_payload({"webhookEvent": "jira:issue_updated"})

    def test_issue_without_key_is_rejected(self) -> None:
        with pytest.raises(UnsupportedEventError):
            normalize_webhook_payload(
                {"webhookEvent": "jira:issue_updated", "issue": {"id": "1"}}
            )


class TestFieldExtraction:
    def test_core_identifiers_are_extracted(self) -> None:
        result = normalize_webhook_payload(_webhook())

        assert result.jira_issue_id == "10101"
        assert result.jira_issue_key == "DEMO-42"
        assert result.project_key == "DEMO"

    def test_nested_names_are_flattened(self) -> None:
        result = normalize_webhook_payload(_webhook())

        assert result.status == "In Progress"
        assert result.priority == "High"
        assert result.assignee == "Ada Lovelace"

    def test_estimate_is_converted_from_seconds_to_hours(self) -> None:
        """Jira devuelve segundos; tratarlos como horas inflaría el impacto por 3600."""
        result = normalize_webhook_payload(_webhook())

        assert result.estimated_hours == 8.0

    def test_labels_are_preserved(self) -> None:
        result = normalize_webhook_payload(_webhook())

        assert result.labels == ["backend", "critico"]

    def test_due_date_only_string_is_parsed(self) -> None:
        result = normalize_webhook_payload(_webhook())

        assert result.due_date == datetime(2026, 8, 15, tzinfo=UTC)

    def test_project_key_is_derived_from_issue_key_when_absent(self) -> None:
        """El webhook no siempre trae el proyecto; la clave del issue lo contiene."""
        payload = _webhook()
        payload["issue"]["fields"].pop("project")

        result = normalize_webhook_payload(payload)

        assert result.project_key == "DEMO"

    def test_missing_optional_fields_become_none(self) -> None:
        payload = _webhook()
        payload["issue"]["fields"] = {"updated": "2026-07-10T11:30:00.000+0000"}

        result = normalize_webhook_payload(payload)

        assert result.summary is None
        assert result.status is None
        assert result.assignee is None
        assert result.due_date is None
        assert result.estimated_hours is None
        assert result.labels == []

    def test_raw_payload_is_preserved_intact(self) -> None:
        """RF-5.6."""
        payload = _webhook()

        result = normalize_webhook_payload(payload)

        assert result.raw_payload == payload


class TestChangelog:
    def test_changed_fields_are_extracted(self) -> None:
        payload = _webhook(
            changelog={
                "items": [
                    {
                        "field": "status",
                        "fromString": "To Do",
                        "toString": "In Progress",
                    },
                    {"field": "duedate", "fromString": None, "toString": "2026-08-15"},
                ]
            }
        )

        result = normalize_webhook_payload(payload)

        assert [item.field for item in result.changed_fields] == ["status", "duedate"]
        assert result.changed_fields[0].from_value == "To Do"
        assert result.changed_fields[0].to_value == "In Progress"

    def test_absent_changelog_yields_empty_list(self) -> None:
        result = normalize_webhook_payload(_webhook())

        assert result.changed_fields == []

    def test_malformed_changelog_is_ignored(self) -> None:
        """Un changelog roto no debe tumbar la ingesta del evento."""
        payload = _webhook(changelog={"items": ["no es un objeto", {}, None]})

        result = normalize_webhook_payload(payload)

        assert result.changed_fields == []


class TestComments:
    def test_plain_text_comment_is_extracted(self) -> None:
        payload = _webhook("comment_created", comment={"body": "Vamos con retraso"})

        result = normalize_webhook_payload(payload)

        assert result.comment_body == "Vamos con retraso"

    def test_adf_comment_is_flattened_to_text(self) -> None:
        """La API v3 devuelve el cuerpo en Atlassian Document Format."""
        payload = _webhook(
            "comment_created",
            comment={
                "body": {
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": "El cliente"},
                                {"type": "text", "text": "pidió una prórroga"},
                            ],
                        }
                    ],
                }
            },
        )

        result = normalize_webhook_payload(payload)

        assert result.comment_body == "El cliente pidió una prórroga"

    def test_comment_absent_yields_none(self) -> None:
        result = normalize_webhook_payload(_webhook())

        assert result.comment_body is None


class TestOccurredAt:
    def test_webhook_timestamp_takes_precedence(self) -> None:
        """Es el dato más fiel al momento del cambio y se repite en los reintentos."""
        result = normalize_webhook_payload(_webhook())

        assert result.occurred_at == datetime.fromtimestamp(1785000000, tz=UTC)

    def test_falls_back_to_updated_when_timestamp_absent(self) -> None:
        payload = _webhook()
        payload.pop("timestamp")

        result = normalize_webhook_payload(payload)

        assert result.occurred_at == datetime(2026, 7, 10, 11, 30, tzinfo=UTC)

    def test_falls_back_to_created_when_updated_absent(self) -> None:
        payload = _webhook()
        payload.pop("timestamp")
        payload["issue"]["fields"].pop("updated")

        result = normalize_webhook_payload(payload)

        assert result.occurred_at == datetime(2026, 7, 1, 9, 0, tzinfo=UTC)

    def test_comment_timestamp_is_preferred_over_issue_timestamp(self) -> None:
        payload = _webhook(
            "comment_created",
            comment={"body": "hola", "created": "2026-07-20T08:00:00.000+0000"},
        )
        payload.pop("timestamp")

        result = normalize_webhook_payload(payload)

        assert result.occurred_at == datetime(2026, 7, 20, 8, 0, tzinfo=UTC)

    def test_result_is_always_timezone_aware_utc(self) -> None:
        result = normalize_webhook_payload(_webhook())

        assert result.occurred_at.tzinfo is not None
        assert result.occurred_at.utcoffset() == UTC.utcoffset(None)


class TestFingerprint:
    """RF-6.1: la huella debe ser determinística y discriminante."""

    def test_same_payload_yields_same_fingerprint(self) -> None:
        first = normalize_webhook_payload(_webhook())
        second = normalize_webhook_payload(_webhook())

        assert first.fingerprint == second.fingerprint

    def test_different_event_type_yields_different_fingerprint(self) -> None:
        created = normalize_webhook_payload(_webhook("jira:issue_created"))
        updated = normalize_webhook_payload(_webhook("jira:issue_updated"))

        assert created.fingerprint != updated.fingerprint

    def test_different_instant_yields_different_fingerprint(self) -> None:
        first = normalize_webhook_payload(_webhook())
        later = _webhook()
        later["timestamp"] = 1785000999000

        assert first.fingerprint != normalize_webhook_payload(later).fingerprint

    def test_different_issue_yields_different_fingerprint(self) -> None:
        first = normalize_webhook_payload(_webhook())
        other = _webhook()
        other["issue"]["id"] = "20202"

        assert first.fingerprint != normalize_webhook_payload(other).fingerprint

    def test_same_instant_in_another_timezone_yields_same_fingerprint(self) -> None:
        """El instante se normaliza a UTC antes de formar la huella."""
        utc_payload = _webhook()
        utc_payload.pop("timestamp")
        utc_payload["issue"]["fields"]["updated"] = "2026-07-10T11:30:00.000+0000"

        offset_payload = _webhook()
        offset_payload.pop("timestamp")
        offset_payload["issue"]["fields"]["updated"] = "2026-07-10T13:30:00.000+0200"

        first = normalize_webhook_payload(utc_payload)
        second = normalize_webhook_payload(offset_payload)

        assert first.fingerprint == second.fingerprint

    def test_fingerprint_is_a_sha256_hex_digest(self) -> None:
        result = normalize_webhook_payload(_webhook())

        assert len(result.fingerprint) == 64
        assert all(char in "0123456789abcdef" for char in result.fingerprint)


class TestRowMapping:
    def test_row_matches_the_table_columns(self) -> None:
        result = normalize_webhook_payload(_webhook())

        row = result.to_row(project_id="11111111-1111-1111-1111-111111111111")

        assert set(row) == {
            "project_id",
            "jira_issue_id",
            "jira_issue_key",
            "event_type",
            "fingerprint",
            "occurred_at",
            "raw_payload",
        }
        assert row["event_type"] == "issue_updated"
        assert row["raw_payload"] == result.raw_payload


class TestJqlSync:
    """RF-4.4 y RF-4.7."""

    def test_issue_is_normalised_as_an_update(self) -> None:
        result = normalize_issue({"id": "10101", "key": "DEMO-42", "fields": _issue_fields()})

        assert result.event_type is EventType.ISSUE_UPDATED
        assert result.jira_issue_key == "DEMO-42"

    def test_sync_uses_the_issue_updated_instant(self) -> None:
        """Es lo que hace la sincronización idempotente."""
        result = normalize_issue({"id": "1", "key": "DEMO-1", "fields": _issue_fields()})

        assert result.occurred_at == datetime(2026, 7, 10, 11, 30, tzinfo=UTC)

    def test_repeating_the_sync_yields_the_same_fingerprint(self) -> None:
        issue = {"id": "1", "key": "DEMO-1", "fields": _issue_fields()}

        first = normalize_issue(issue)
        second = normalize_issue(issue)

        assert first.fingerprint == second.fingerprint

    def test_issue_without_key_is_rejected(self) -> None:
        with pytest.raises(UnsupportedEventError):
            normalize_issue({"id": "1", "fields": {}})


class TestParsingHelpers:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("", None),
            ("no es una fecha", None),
            (12345, None),
        ],
    )
    def test_unparseable_dates_return_none(self, value: Any, expected: None) -> None:
        """Una fecha ilegible no debe tumbar la ingesta del evento."""
        assert parse_jira_datetime(value) is expected

    def test_naive_datetime_is_assumed_utc(self) -> None:
        result = parse_jira_datetime("2026-07-10T11:30:00")

        assert result is not None
        assert result.tzinfo is not None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (3600, 1.0),
            (28800, 8.0),
            (1800, 0.5),
            (0, 0.0),
            (None, None),
            ("no es un numero", None),
            (-100, None),
        ],
    )
    def test_seconds_to_hours(self, value: Any, expected: float | None) -> None:
        assert seconds_to_hours(value) == expected
