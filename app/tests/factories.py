"""Constructores de datos para los tests.

Centraliza la forma de un evento y de un contexto para que un cambio en el modelo se arregle en
un sitio y no en doscientos.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.agents.base import AgentContext
from app.schemas.analysis import CommitmentSnapshot, CommitmentStatus, ProjectSnapshot
from app.schemas.events import EventKind, ExternalEvent, FieldChange, ProviderName

#: Instante de referencia fijo. Las pruebas de tiempo inyectan ``now`` por contexto en lugar de
#: parchear ``datetime``, lo que hace deterministas los casos de vencimiento.
NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def make_event(**overrides: Any) -> ExternalEvent:
    """Evento del dominio con valores razonables."""
    values: dict[str, Any] = {
        "provider": ProviderName.JIRA,
        "workspace_key": "DEMO",
        "external_id": "10101",
        "external_key": "DEMO-42",
        "kind": EventKind.WORK_ITEM_UPDATED,
        "occurred_at": NOW,
        "title": "Entregar el informe",
        "state": "In Progress",
        "owner": "Ada Lovelace",
        "priority": "High",
        "due_date": NOW + timedelta(days=30),
        "estimated_hours": 8.0,
        "labels": [],
        "changes": [],
        "raw_payload": {},
    }
    values.update(overrides)
    return ExternalEvent(**values)


def make_context(**overrides: Any) -> AgentContext:
    """Contexto de análisis con un proyecto que sí tiene coste por hora."""
    event = overrides.pop("event", None) or make_event()
    values: dict[str, Any] = {
        "event": event,
        "now": NOW,
        "project": ProjectSnapshot(
            jira_project_key=event.workspace_key, hourly_cost=50.0
        ),
        "commitment": None,
        "recent_events": [],
    }
    values.update(overrides)
    return AgentContext(**values)


def make_commitment(**overrides: Any) -> CommitmentSnapshot:
    values: dict[str, Any] = {
        "jira_issue_key": "DEMO-42",
        "title": "Entregar el informe",
        "due_date": NOW + timedelta(days=30),
        "status": CommitmentStatus.OPEN,
        "estimated_hours": 8.0,
    }
    values.update(overrides)
    return CommitmentSnapshot(**values)


def status_change(from_value: str, to_value: str) -> FieldChange:
    return FieldChange(field="status", from_value=from_value, to_value=to_value)


def jira_webhook(
    event: str = "jira:issue_updated", issue_id: str = "10101", **extra: Any
) -> dict[str, Any]:
    """Payload de webhook de Jira, en su forma real."""
    payload: dict[str, Any] = {
        "webhookEvent": event,
        "timestamp": 1785000000000,
        "issue": {
            "id": issue_id,
            "key": "DEMO-42",
            "fields": {
                "summary": "Entregar el informe",
                "status": {"name": "In Progress"},
                "assignee": {"displayName": "Ada Lovelace"},
                "priority": {"name": "High"},
                "duedate": "2026-08-15",
                "timeoriginalestimate": 28800,
                "labels": ["backend"],
                "created": "2026-07-01T09:00:00.000+0000",
                "updated": "2026-07-10T11:30:00.000+0000",
                "project": {"key": "DEMO"},
            },
        },
    }
    payload.update(extra)
    return payload
