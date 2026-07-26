"""Constructores de dominio para los tests de agentes especializados.

Centraliza la creación de ``AgentContext``, ``CommitmentSnapshot`` y señales de
provider para que los tests expresen solo la variación que prueban.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from app.agents.specialized.base import AgentContext
from app.schemas.domain import CommitmentSnapshot, Priority, ProjectSnapshot

#: Instante determinista. Los agentes reciben ``now`` por contexto.
NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)

#: UUID fijo para tests que no necesitan uno random.
FIXED_UUID = UUID("00000000-0000-0000-0000-000000000001")
PROJECT_UUID = UUID("00000000-0000-0000-0000-000000000002")

#: Ruta al seed financiero.
FINANCE_SEED_PATH = Path(__file__).resolve().parents[2] / "db" / "seed" / "finance_seed.json"


def make_commitment(**overrides: Any) -> CommitmentSnapshot:
    """Commitment con valores razonables. Sobreescribe solo lo que varía."""
    defaults: dict[str, Any] = {
        "id": FIXED_UUID,
        "project_id": PROJECT_UUID,
        "title": "Entregar integración de pagos empresariales antes del viernes",
        "due_date": NOW + timedelta(days=5),
        "financial_exposure": Decimal("20000"),
        "currency": "USD",
        "priority": Priority.HIGH,
        "owner": "Ada Lovelace",
        "beneficiary": "Cliente Acme",
    }
    defaults.update(overrides)
    return CommitmentSnapshot(**defaults)


def make_project(**overrides: Any) -> ProjectSnapshot:
    defaults: dict[str, Any] = {
        "id": PROJECT_UUID,
        "name": "Pagos Empresariales",
        "hourly_cost": Decimal("75"),
        "currency": "USD",
        "external_references": {"jira": "DAT", "github": "datgent/payments"},
    }
    defaults.update(overrides)
    return ProjectSnapshot(**defaults)


def make_context(
    *,
    signals: dict[str, Any] | None = None,
    commitment: CommitmentSnapshot | None = None,
    project: ProjectSnapshot | None = None,
    now: datetime | None = None,
    **overrides: Any,
) -> AgentContext:
    """AgentContext listo para pasar a un agente."""
    return AgentContext(
        commitment=commitment or make_commitment(**overrides.pop("commitment_kw", {})),
        project=project or make_project(),
        now=now or NOW,
        signals=signals or {},
        recent_events=overrides.get("recent_events", []),
        documents=overrides.get("documents", []),
    )


# --- Señales por provider ----------------------------------------------------------


def jira_signal(
    *,
    issue_key: str = "DAT-42",
    status: str = "In Progress",
    assignee: str | None = "Ada Lovelace",
    due_date: str | None = None,
    blocked_by: list[str] | None = None,
    last_activity_at: str | None = None,
    reassignment_count: int = 0,
    reopened: bool = False,
    story_points: int | None = 5,
    estimated_hours: float | None = None,
    url: str | None = "https://jira.example.com/DAT-42",
    **extra: Any,
) -> dict[str, Any]:
    sig: dict[str, Any] = {
        "issue_key": issue_key,
        "status": status,
        "assignee": assignee,
        "due_date": due_date,
        "blocked_by": blocked_by or [],
        "last_activity_at": last_activity_at,
        "reassignment_count": reassignment_count,
        "reopened": reopened,
        "story_points": story_points,
        "estimated_hours": estimated_hours,
        "url": url,
    }
    sig.update(extra)
    return sig


def github_signal(
    *,
    repository: str = "datgent/payments",
    pull_requests: list[dict[str, Any]] | None = None,
    checks: list[dict[str, Any]] | None = None,
    changed_files: list[str] | None = None,
    coverage: float | None = 85.0,
    migrations: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    sig: dict[str, Any] = {
        "repository": repository,
        "pull_requests": pull_requests or [],
        "checks": checks or [],
        "changed_files": changed_files or [],
        "coverage": coverage,
        "migrations": migrations or [],
    }
    sig.update(extra)
    return sig


def supabase_signal(
    *,
    tables: list[dict[str, Any]] | None = None,
    migrations: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    sig: dict[str, Any] = {
        "tables": tables or [],
        "migrations": migrations or [],
    }
    sig.update(extra)
    return sig


def finance_signal(snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Señal del provider financiero. Si no se pasa snapshot, usa el seed."""
    if snapshot is None:
        snapshot = json.loads(FINANCE_SEED_PATH.read_text())
    return {"snapshot": snapshot}


def make_open_pr(
    *,
    number: int = 1,
    state: str = "open",
    mergeable: bool = True,
    has_conflicts: bool = False,
    approved_reviews: int = 0,
    created_at: str | None = None,
    additions: int = 50,
    deletions: int = 20,
    url: str = "https://github.com/datgent/payments/pull/1",
    **extra: Any,
) -> dict[str, Any]:
    pr: dict[str, Any] = {
        "number": number,
        "state": state,
        "mergeable": mergeable,
        "has_conflicts": has_conflicts,
        "approved_reviews": approved_reviews,
        "created_at": created_at or (NOW - timedelta(hours=12)).isoformat(),
        "additions": additions,
        "deletions": deletions,
        "url": url,
    }
    pr.update(extra)
    return pr


def make_table(
    *,
    name: str = "payments",
    rls_enabled: bool = True,
    policies: list[dict[str, Any]] | None = None,
    row_count: int | None = 5000,
    filtered_columns: list[str] | None = None,
    indexed_columns: list[str] | None = None,
    missing_foreign_keys: list[str] | None = None,
    orphan_rows: int = 0,
    **extra: Any,
) -> dict[str, Any]:
    tbl: dict[str, Any] = {
        "name": name,
        "rls_enabled": rls_enabled,
        "policies": policies or [],
        "row_count": row_count,
        "filtered_columns": filtered_columns or [],
        "indexed_columns": indexed_columns or [],
        "missing_foreign_keys": missing_foreign_keys,
        "orphan_rows": orphan_rows,
    }
    tbl.update(extra)
    return tbl
