"""Tests exhaustivos de los 4 agentes especializados de Datgent.

Garantiza que cada agente cumple el contrato: sin señal -> SKIPPED, cada código
se dispara/no se dispara, evidencia presente, score=MAX, confianza ponderada,
acciones requieren aprobación humana.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.agents.specialized.base import AgentContext
from app.agents.specialized.code_agent import (
    COVERAGE_FLOOR,
    CodeAgent,
    LARGE_DIFF_LINES,
    STALE_PR_DAYS,
    _looks_like_test,
)
from app.agents.specialized.database_agent import (
    DatabaseAgent,
    INDEX_ROW_THRESHOLD,
    _is_permissive,
)
from app.agents.specialized.finance_agent import ESCALATION_EXPOSURE, FinanceAgent
from app.agents.specialized.jira_agent import (
    DUE_SOON_DAYS,
    JiraAgent,
    REASSIGNMENT_THRESHOLD,
    STALE_DAYS,
    WEIGHT_BLOCKED,
    WEIGHT_OVERDUE,
    _as_datetime,
)
from app.schemas.domain import AgentRunStatus, Severity
from app.tests.factories_domain import (
    FINANCE_SEED_PATH,
    NOW,
    finance_signal,
    github_signal,
    jira_signal,
    make_commitment,
    make_context,
    make_open_pr,
    make_table,
    supabase_signal,
)


# =============================================================================
# JiraAgent
# =============================================================================


class TestJiraAgentSkipped:
    """Sin señal de Jira el agente declara que no puede concluir."""

    def test_sin_signal_status_skipped(self):
        """Garantiza status SKIPPED cuando no hay datos de Jira."""
        ctx = make_context(signals={})
        out = JiraAgent().analyze(ctx)
        assert out.status == AgentRunStatus.SKIPPED

    def test_sin_signal_confidence_cero(self):
        """Confianza 0 porque no hay datos — no es 'sin problemas'."""
        ctx = make_context(signals={})
        out = JiraAgent().analyze(ctx)
        assert out.confidence == 0.0

    def test_sin_signal_missing_no_vacio(self):
        """Debe declarar qué le falta."""
        ctx = make_context(signals={})
        out = JiraAgent().analyze(ctx)
        assert len(out.missing_information) > 0

    def test_sin_signal_score_cero(self):
        """Score 0: no afirma que haya riesgo."""
        ctx = make_context(signals={})
        out = JiraAgent().analyze(ctx)
        assert out.risk_score == 0


class TestJiraOverdue:
    """El issue venció y sigue abierto."""

    def test_dispara_cuando_vencido(self):
        """due_date en el pasado -> finding overdue."""
        ctx = make_context(
            signals={"jira": jira_signal()},
            commitment_kw={"due_date": NOW - timedelta(days=2)},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "overdue" in codes

    def test_no_dispara_cuando_no_vencido(self):
        """due_date en el futuro -> NO overdue."""
        ctx = make_context(
            signals={"jira": jira_signal()},
            commitment_kw={"due_date": NOW + timedelta(days=10)},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "overdue" not in codes


class TestJiraDueToday:
    """Vence hoy (< 1 día)."""

    def test_dispara_due_today(self):
        """delta < 1 día -> due_today."""
        ctx = make_context(
            signals={"jira": jira_signal()},
            commitment_kw={"due_date": NOW + timedelta(hours=12)},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "due_today" in codes

    def test_no_dispara_due_today_si_queda_mas_de_un_dia(self):
        """delta > 1 día -> NO due_today."""
        ctx = make_context(
            signals={"jira": jira_signal()},
            commitment_kw={"due_date": NOW + timedelta(days=2)},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "due_today" not in codes


class TestJiraDueSoon:
    """Vence dentro de DUE_SOON_DAYS."""

    def test_dispara_en_frontera(self):
        """Exactamente DUE_SOON_DAYS días -> due_soon (delta <= umbral)."""
        ctx = make_context(
            signals={"jira": jira_signal()},
            commitment_kw={"due_date": NOW + timedelta(days=DUE_SOON_DAYS)},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "due_soon" in codes

    def test_no_dispara_justo_fuera(self):
        """DUE_SOON_DAYS + 1 día -> NO due_soon."""
        ctx = make_context(
            signals={"jira": jira_signal()},
            commitment_kw={"due_date": NOW + timedelta(days=DUE_SOON_DAYS + 1)},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "due_soon" not in codes


class TestJiraNoDueDate:
    """Sin fecha de vencimiento en compromiso ni issue."""

    def test_dispara_no_due_date(self):
        ctx = make_context(
            signals={"jira": jira_signal(due_date=None)},
            commitment_kw={"due_date": None},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "no_due_date" in codes

    def test_no_dispara_si_commitment_tiene_fecha(self):
        """El commitment tiene due_date -> NO se dispara."""
        ctx = make_context(
            signals={"jira": jira_signal(due_date=None)},
            commitment_kw={"due_date": NOW + timedelta(days=10)},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "no_due_date" not in codes


class TestJiraBlocked:
    def test_dispara_blocked(self):
        ctx = make_context(signals={"jira": jira_signal(status="Blocked")})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "blocked" in codes

    def test_no_dispara_si_estado_normal(self):
        ctx = make_context(signals={"jira": jira_signal(status="In Progress")})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "blocked" not in codes


class TestJiraUnassigned:
    def test_dispara_unassigned(self):
        ctx = make_context(signals={"jira": jira_signal(assignee=None)})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "unassigned" in codes

    def test_no_dispara_si_tiene_assignee(self):
        ctx = make_context(signals={"jira": jira_signal(assignee="Ada")})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "unassigned" not in codes


class TestJiraExternalDependency:
    def test_dispara_external_dependency(self):
        ctx = make_context(
            signals={"jira": jira_signal(blocked_by=["EXTERNAL-vendor-api"])}
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "external_dependency" in codes

    def test_no_dispara_sin_dependencias_externas(self):
        ctx = make_context(signals={"jira": jira_signal(blocked_by=["DAT-100"])})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "external_dependency" not in codes


class TestJiraStale:
    def test_dispara_en_frontera(self):
        """Exactamente STALE_DAYS -> stale."""
        last = (NOW - timedelta(days=STALE_DAYS)).isoformat()
        ctx = make_context(signals={"jira": jira_signal(last_activity_at=last)})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "stale" in codes

    def test_no_dispara_justo_debajo(self):
        """STALE_DAYS - 1 -> NO stale."""
        last = (NOW - timedelta(days=STALE_DAYS - 1)).isoformat()
        ctx = make_context(signals={"jira": jira_signal(last_activity_at=last)})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "stale" not in codes


class TestJiraReassignmentChurn:
    def test_dispara_en_frontera(self):
        """Exactamente REASSIGNMENT_THRESHOLD -> reassignment_churn."""
        ctx = make_context(
            signals={"jira": jira_signal(reassignment_count=REASSIGNMENT_THRESHOLD)}
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "reassignment_churn" in codes

    def test_no_dispara_justo_debajo(self):
        ctx = make_context(
            signals={"jira": jira_signal(reassignment_count=REASSIGNMENT_THRESHOLD - 1)}
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "reassignment_churn" not in codes


class TestJiraReopened:
    def test_dispara_reopened(self):
        ctx = make_context(signals={"jira": jira_signal(reopened=True)})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "reopened" in codes

    def test_no_dispara_si_no_reopened(self):
        ctx = make_context(signals={"jira": jira_signal(reopened=False)})
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "reopened" not in codes


class TestJiraDueDatePriority:
    """La due_date del commitment tiene prioridad sobre la del issue."""

    def test_commitment_due_date_manda(self):
        """Issue dice futuro, commitment dice pasado -> overdue."""
        ctx = make_context(
            signals={"jira": jira_signal(due_date=(NOW + timedelta(days=30)).isoformat())},
            commitment_kw={"due_date": NOW - timedelta(days=1)},
        )
        out = JiraAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "overdue" in codes


class TestJiraAsDatetime:
    """_as_datetime tolera ISO con Z, datetime, y basura."""

    def test_iso_con_z(self):
        result = _as_datetime("2026-07-25T12:00:00Z")
        assert isinstance(result, datetime)

    def test_datetime_pass_through(self):
        dt = datetime(2026, 7, 25, tzinfo=UTC)
        assert _as_datetime(dt) is dt

    def test_basura_devuelve_none(self):
        assert _as_datetime("not-a-date") is None

    def test_none_devuelve_none(self):
        assert _as_datetime(None) is None


class TestJiraScoreIsMax:
    """El score del agente es el MÁXIMO de sus findings, no la suma."""

    def test_score_es_maximo(self):
        ctx = make_context(
            signals={"jira": jira_signal(status="Blocked", assignee=None)},
            commitment_kw={"due_date": NOW - timedelta(days=1)},
        )
        out = JiraAgent().analyze(ctx)
        max_finding = max(f.risk_score for f in out.findings)
        assert out.risk_score == max_finding


class TestJiraConfidencePonderada:
    """Confianza es media ponderada por riesgo."""

    def test_confianza_no_es_simple_average(self):
        """Con external_dependency (conf 0.75) + overdue (conf 1.0) la media
        ponderada se inclina hacia overdue por su mayor score."""
        ctx = make_context(
            signals={"jira": jira_signal(blocked_by=["external-vendor-x"])},
            commitment_kw={"due_date": NOW - timedelta(days=1)},
        )
        out = JiraAgent().analyze(ctx)
        # La confianza debe estar entre 0.75 y 1.0 (ponderada hacia 1.0)
        assert 0.75 < out.confidence <= 1.0


class TestJiraEvidencePresente:
    """Todo finding lleva al menos una Evidence con explanation no vacía."""

    def test_findings_tienen_evidence(self):
        ctx = make_context(
            signals={"jira": jira_signal(status="Blocked", assignee=None, reopened=True)},
            commitment_kw={"due_date": NOW - timedelta(days=1)},
        )
        out = JiraAgent().analyze(ctx)
        for finding in out.findings:
            assert len(finding.evidence) >= 1
            for ev in finding.evidence:
                assert ev.explanation != ""


class TestJiraActionsRequireApproval:
    """Todas las acciones requieren aprobación humana."""

    def test_actions_require_human_approval(self):
        ctx = make_context(
            signals={"jira": jira_signal(status="Blocked", assignee=None)}
        )
        out = JiraAgent().analyze(ctx)
        for action in out.recommended_actions:
            assert action.requires_human_approval is True


# =============================================================================
# CodeAgent
# =============================================================================


class TestCodeAgentSkipped:
    """Sin señal de GitHub -> SKIPPED."""

    def test_status_skipped(self):
        ctx = make_context(signals={})
        out = CodeAgent().analyze(ctx)
        assert out.status == AgentRunStatus.SKIPPED

    def test_confidence_cero(self):
        ctx = make_context(signals={})
        out = CodeAgent().analyze(ctx)
        assert out.confidence == 0.0

    def test_missing_no_vacio(self):
        ctx = make_context(signals={})
        out = CodeAgent().analyze(ctx)
        assert len(out.missing_information) > 0

    def test_score_cero(self):
        ctx = make_context(signals={})
        out = CodeAgent().analyze(ctx)
        assert out.risk_score == 0


class TestCodePrBlocked:
    def test_dispara_pr_blocked(self):
        """PR abierto no mergeable -> pr_blocked."""
        pr = make_open_pr(mergeable=False)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "pr_blocked" in codes

    def test_no_dispara_si_mergeable(self):
        pr = make_open_pr(mergeable=True, has_conflicts=False)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "pr_blocked" not in codes


class TestCodeNoReview:
    def test_dispara_no_review(self):
        pr = make_open_pr(approved_reviews=0)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "no_review" in codes

    def test_no_dispara_con_reviews(self):
        pr = make_open_pr(approved_reviews=2)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "no_review" not in codes


class TestCodeStalePr:
    def test_dispara_en_frontera(self):
        """PR abierto exactamente STALE_PR_DAYS -> stale_pr."""
        created = (NOW - timedelta(days=STALE_PR_DAYS)).isoformat()
        pr = make_open_pr(created_at=created)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "stale_pr" in codes

    def test_no_dispara_justo_debajo(self):
        created = (NOW - timedelta(days=STALE_PR_DAYS - 1)).isoformat()
        pr = make_open_pr(created_at=created)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "stale_pr" not in codes


class TestCodePrOpenNearDue:
    def test_dispara_pr_open_near_due(self):
        """PR abierto a menos de 2 días del vencimiento."""
        pr = make_open_pr()
        ctx = make_context(
            signals={"github": github_signal(pull_requests=[pr])},
            commitment_kw={"due_date": NOW + timedelta(days=1)},
        )
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "pr_open_near_due" in codes

    def test_no_dispara_si_due_date_lejana(self):
        pr = make_open_pr()
        ctx = make_context(
            signals={"github": github_signal(pull_requests=[pr])},
            commitment_kw={"due_date": NOW + timedelta(days=10)},
        )
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "pr_open_near_due" not in codes


class TestCodeLargeDiff:
    def test_dispara_en_frontera(self):
        """Exactamente LARGE_DIFF_LINES -> large_diff."""
        pr = make_open_pr(additions=LARGE_DIFF_LINES, deletions=0)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "large_diff" in codes

    def test_no_dispara_justo_debajo(self):
        pr = make_open_pr(additions=LARGE_DIFF_LINES - 1, deletions=0)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "large_diff" not in codes


class TestCodeFailingChecks:
    def test_dispara_failing_checks(self):
        checks = [{"name": "ci-lint", "conclusion": "failure"}]
        ctx = make_context(signals={"github": github_signal(checks=checks)})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "failing_checks" in codes

    def test_no_dispara_checks_ok(self):
        checks = [{"name": "ci-lint", "conclusion": "success"}]
        ctx = make_context(signals={"github": github_signal(checks=checks)})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "failing_checks" not in codes


class TestCodeNoTests:
    def test_dispara_no_tests(self):
        """Cambios sin ficheros de test -> no_tests."""
        ctx = make_context(
            signals={"github": github_signal(changed_files=["src/main.py", "src/util.py"])}
        )
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "no_tests" in codes

    def test_no_dispara_con_tests(self):
        ctx = make_context(
            signals={"github": github_signal(changed_files=["src/main.py", "tests/test_main.py"])}
        )
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "no_tests" not in codes


class TestCodeLowCoverage:
    def test_dispara_bajo_floor(self):
        """Cobertura justo debajo de COVERAGE_FLOOR."""
        ctx = make_context(
            signals={"github": github_signal(coverage=COVERAGE_FLOOR - 1)}
        )
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "low_coverage" in codes

    def test_no_dispara_en_floor(self):
        """Exactamente COVERAGE_FLOOR NO dispara."""
        ctx = make_context(
            signals={"github": github_signal(coverage=COVERAGE_FLOOR)}
        )
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "low_coverage" not in codes


class TestCodeRiskyMigration:
    def test_dispara_sin_rollback(self):
        mig = {"path": "migrations/001.sql", "content": "DROP TABLE users;", "has_rollback": False}
        ctx = make_context(signals={"github": github_signal(migrations=[mig])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "risky_migration" in codes

    def test_no_dispara_con_rollback(self):
        """Migración destructiva CON rollback NO dispara."""
        mig = {"path": "migrations/001.sql", "content": "DROP TABLE users;", "has_rollback": True}
        ctx = make_context(signals={"github": github_signal(migrations=[mig])})
        out = CodeAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "risky_migration" not in codes


class TestCodePrCerradoIgnorado:
    """Un PR cerrado no genera findings de PR."""

    def test_pr_cerrado_ignorado(self):
        pr = make_open_pr(state="closed", mergeable=False, approved_reviews=0)
        ctx = make_context(signals={"github": github_signal(pull_requests=[pr])})
        out = CodeAgent().analyze(ctx)
        pr_codes = {"pr_blocked", "no_review", "stale_pr", "pr_open_near_due", "large_diff"}
        found_codes = {f.code for f in out.findings}
        assert found_codes & pr_codes == set()


class TestCodeLooksLikeTest:
    """_looks_like_test reconoce py/js/go."""

    def test_python_test(self):
        assert _looks_like_test("tests/test_main.py") is True

    def test_js_spec(self):
        assert _looks_like_test("src/app.spec.ts") is True

    def test_go_test(self):
        assert _looks_like_test("pkg/handler_test.go") is True

    def test_regular_file(self):
        assert _looks_like_test("src/main.py") is False


class TestCodeScoreIsMax:
    def test_score_es_maximo(self):
        checks = [{"name": "ci", "conclusion": "failure"}]
        mig = {"path": "m.sql", "content": "drop table x;", "has_rollback": False}
        ctx = make_context(
            signals={"github": github_signal(checks=checks, migrations=[mig])}
        )
        out = CodeAgent().analyze(ctx)
        max_finding = max(f.risk_score for f in out.findings)
        assert out.risk_score == max_finding


class TestCodeEvidencePresente:
    def test_findings_tienen_evidence(self):
        checks = [{"name": "ci", "conclusion": "failure"}]
        ctx = make_context(signals={"github": github_signal(checks=checks)})
        out = CodeAgent().analyze(ctx)
        for finding in out.findings:
            assert len(finding.evidence) >= 1
            for ev in finding.evidence:
                assert ev.explanation != ""


class TestCodeActionsRequireApproval:
    def test_actions_require_human_approval(self):
        mig = {"path": "m.sql", "content": "drop table x;", "has_rollback": False}
        ctx = make_context(signals={"github": github_signal(migrations=[mig])})
        out = CodeAgent().analyze(ctx)
        for action in out.recommended_actions:
            assert action.requires_human_approval is True


# =============================================================================
# FinanceAgent
# =============================================================================


class TestFinanceAgentSkipped:
    """Sin snapshot financiero -> SKIPPED."""

    def test_sin_signal_status_skipped(self):
        ctx = make_context(signals={})
        out = FinanceAgent().analyze(ctx)
        assert out.status == AgentRunStatus.SKIPPED

    def test_sin_signal_confidence_cero(self):
        ctx = make_context(signals={})
        out = FinanceAgent().analyze(ctx)
        assert out.confidence == 0.0

    def test_sin_signal_missing_no_vacio(self):
        ctx = make_context(signals={})
        out = FinanceAgent().analyze(ctx)
        assert len(out.missing_information) > 0

    def test_sin_signal_score_cero(self):
        ctx = make_context(signals={})
        out = FinanceAgent().analyze(ctx)
        assert out.risk_score == 0

    def test_snapshot_invalido_skipped_con_motivo_distinto(self):
        """Snapshot inválido -> SKIPPED con motivo diferente al de ausente."""
        ctx = make_context(signals={"finance": {"snapshot": {"bad": "data"}}})
        out = FinanceAgent().analyze(ctx)
        assert out.status == AgentRunStatus.SKIPPED
        # El motivo menciona "no son válidos", diferente al de "falta la señal"
        ctx_sin = make_context(signals={})
        out_sin = FinanceAgent().analyze(ctx_sin)
        assert out.summary != out_sin.summary


class TestFinanceSeedSeverity:
    """Con el seed de finance_seed.json la severidad debe ser alta o crítica."""

    def test_seed_severidad_alta_o_critica(self):
        ctx = make_context(signals={"finance": finance_signal()})
        out = FinanceAgent().analyze(ctx)
        assert out.severity in (Severity.HIGH, Severity.CRITICAL)


class TestFinanceEscalation:
    """Exposición > ESCALATION_EXPOSURE -> recomienda renegotiate_scope."""

    def test_propone_renegotiate_scope(self):
        ctx = make_context(signals={"finance": finance_signal()})
        out = FinanceAgent().analyze(ctx)
        action_types = [a.action_type for a in out.recommended_actions]
        assert "renegotiate_scope" in action_types

    def test_no_propone_si_exposure_baja(self):
        """Sin penalizaciones ni retenciones altas no propone renegociar."""
        snapshot = {
            "project_key": "SMALL",
            "commitment_ref": "Pequeño",
            "currency": "USD",
            "budget_lines": [{"concept": "Dev", "planned": "5000", "actual": "2000", "currency": "USD", "category": "dev"}],
            "labor_entries": [],
            "penalties": [],
            "retained_payments": "0",
            "period_start": "2026-07-14",
            "period_end": "2026-07-25",
        }
        ctx = make_context(signals={"finance": {"snapshot": snapshot}})
        out = FinanceAgent().analyze(ctx)
        action_types = [a.action_type for a in out.recommended_actions]
        assert "renegotiate_scope" not in action_types


class TestFinanceNoRecalcula:
    """El FinanceAgent NO recalcula: los findings vienen del service."""

    def test_findings_vienen_del_service(self):
        """Los findings deben tener codes del finance_analysis_service."""
        ctx = make_context(signals={"finance": finance_signal()})
        out = FinanceAgent().analyze(ctx)
        # Verificar que hay findings con codes del servicio financiero
        valid_codes = {"budget_overrun", "negative_margin", "high_burn_rate",
                       "penalty_exposure", "retained_payment_risk", "overtime_projected"}
        found_codes = {f.code for f in out.findings}
        assert found_codes.issubset(valid_codes)
        assert len(found_codes) > 0


class TestFinanceScoreIsMax:
    def test_score_es_maximo(self):
        ctx = make_context(signals={"finance": finance_signal()})
        out = FinanceAgent().analyze(ctx)
        if out.findings:
            max_finding = max(f.risk_score for f in out.findings)
            assert out.risk_score == max_finding


class TestFinanceActionsRequireApproval:
    def test_actions_require_human_approval(self):
        ctx = make_context(signals={"finance": finance_signal()})
        out = FinanceAgent().analyze(ctx)
        for action in out.recommended_actions:
            assert action.requires_human_approval is True


# =============================================================================
# DatabaseAgent
# =============================================================================


class TestDatabaseAgentSkipped:
    """Sin señal de Supabase -> SKIPPED."""

    def test_status_skipped(self):
        ctx = make_context(signals={})
        out = DatabaseAgent().analyze(ctx)
        assert out.status == AgentRunStatus.SKIPPED

    def test_confidence_cero(self):
        ctx = make_context(signals={})
        out = DatabaseAgent().analyze(ctx)
        assert out.confidence == 0.0

    def test_missing_no_vacio(self):
        ctx = make_context(signals={})
        out = DatabaseAgent().analyze(ctx)
        assert len(out.missing_information) > 0

    def test_score_cero(self):
        ctx = make_context(signals={})
        out = DatabaseAgent().analyze(ctx)
        assert out.risk_score == 0


class TestDbMissingRls:
    def test_dispara_missing_rls(self):
        tbl = make_table(rls_enabled=False)
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "missing_rls" in codes

    def test_no_dispara_con_rls_activo(self):
        """Tabla con RLS activo y sin políticas permisivas -> nada."""
        tbl = make_table(rls_enabled=True, policies=[])
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "missing_rls" not in codes
        assert "permissive_rls" not in codes


class TestDbPermissiveRls:
    def test_dispara_permissive_rls(self):
        policy = {"name": "allow_all", "definition": "using (true)", "roles": "anon"}
        tbl = make_table(rls_enabled=True, policies=[policy])
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "permissive_rls" in codes

    def test_no_dispara_para_authenticated(self):
        """using(true) para authenticated NO es permisiva."""
        policy = {"name": "auth_all", "definition": "using (true)", "roles": "authenticated"}
        tbl = make_table(rls_enabled=True, policies=[policy])
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "permissive_rls" not in codes


class TestDbIsPermissive:
    """_is_permissive detecta using(true) para anon pero NO para authenticated."""

    def test_anon_true(self):
        policy = {"definition": "using(true)", "roles": "anon"}
        assert _is_permissive(policy) is True

    def test_public_true(self):
        policy = {"definition": "using (true)", "roles": "public"}
        assert _is_permissive(policy) is True

    def test_authenticated_no_permissive(self):
        policy = {"definition": "using(true)", "roles": "authenticated"}
        assert _is_permissive(policy) is False

    def test_restrictive_policy(self):
        policy = {"definition": "using (user_id = auth.uid())", "roles": "anon"}
        assert _is_permissive(policy) is False


class TestDbMigrationNoRollback:
    def test_dispara_migration_no_rollback(self):
        mig = {"name": "001_create_tables", "has_rollback": False}
        ctx = make_context(signals={"supabase": supabase_signal(migrations=[mig])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "migration_no_rollback" in codes

    def test_no_dispara_con_rollback(self):
        mig = {"name": "001_create_tables", "has_rollback": True}
        ctx = make_context(signals={"supabase": supabase_signal(migrations=[mig])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "migration_no_rollback" not in codes


class TestDbMissingIndex:
    def test_dispara_en_frontera(self):
        """Exactamente INDEX_ROW_THRESHOLD filas + columna sin índice -> missing_index."""
        tbl = make_table(
            row_count=INDEX_ROW_THRESHOLD,
            filtered_columns=["user_id"],
            indexed_columns=[],
        )
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "missing_index" in codes

    def test_no_dispara_justo_debajo(self):
        tbl = make_table(
            row_count=INDEX_ROW_THRESHOLD - 1,
            filtered_columns=["user_id"],
            indexed_columns=[],
        )
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "missing_index" not in codes

    def test_row_count_none_va_a_missing_information(self):
        """row_count None -> missing_information, NO finding."""
        tbl = make_table(row_count=None, filtered_columns=["user_id"], indexed_columns=[])
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "missing_index" not in codes
        assert any("filas" in m for m in out.missing_information)


class TestDbMissingConstraint:
    def test_dispara_missing_constraint(self):
        tbl = make_table(missing_foreign_keys=["project_id"])
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "missing_constraint" in codes

    def test_no_dispara_sin_fks_faltantes(self):
        tbl = make_table(missing_foreign_keys=None)
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "missing_constraint" not in codes


class TestDbOrphanRows:
    def test_dispara_orphan_rows(self):
        tbl = make_table(orphan_rows=15)
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "orphan_rows" in codes

    def test_no_dispara_sin_orphans(self):
        tbl = make_table(orphan_rows=0)
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        codes = [f.code for f in out.findings]
        assert "orphan_rows" not in codes


class TestDbScoreIsMax:
    def test_score_es_maximo(self):
        tbl = make_table(rls_enabled=False, orphan_rows=5)
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        max_finding = max(f.risk_score for f in out.findings)
        assert out.risk_score == max_finding


class TestDbEvidencePresente:
    def test_findings_tienen_evidence(self):
        tbl = make_table(rls_enabled=False)
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        for finding in out.findings:
            assert len(finding.evidence) >= 1
            for ev in finding.evidence:
                assert ev.explanation != ""


class TestDbActionsRequireApproval:
    def test_actions_require_human_approval(self):
        tbl = make_table(rls_enabled=False)
        ctx = make_context(signals={"supabase": supabase_signal(tables=[tbl])})
        out = DatabaseAgent().analyze(ctx)
        for action in out.recommended_actions:
            assert action.requires_human_approval is True
