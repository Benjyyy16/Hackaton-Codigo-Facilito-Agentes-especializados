"""Tests exhaustivos del orquestador de riesgo de Datgent.

Garantiza que: consolidación de scores respeta pesos, corroboración, confianza
penalizada por cobertura, cadena causal, pre-mortem, 3 escenarios, y el caso demo.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from app.agents.risk_orchestrator import (
    AGENT_WEIGHTS,
    CORROBORATION_BONUS_PER_AGENT,
    CORROBORATION_THRESHOLD,
    MAX_CORROBORATION_BONUS,
    RiskOrchestrator,
)
from app.agents.specialized.base import AgentContext, BaseSpecializedAgent
from app.agents.specialized.code_agent import CodeAgent
from app.agents.specialized.jira_agent import JiraAgent
from app.schemas.domain import (
    AgentOutput,
    AgentRunStatus,
    Finding,
    RiskCase,
    Scenario,
    ScenarioKind,
    Severity,
)
from app.tests.factories_domain import (
    NOW,
    finance_signal,
    github_signal,
    jira_signal,
    make_commitment,
    make_context,
    make_open_pr,
    make_project,
    make_table,
    supabase_signal,
)


# --- Helpers -------------------------------------------------------------------


class FailingAgent(BaseSpecializedAgent):
    """Agente que siempre eleva excepción."""
    name = "failing-agent"
    category = "test"

    def analyze(self, context: AgentContext) -> AgentOutput:
        raise RuntimeError("fallo deliberado")


class FixedAgent(BaseSpecializedAgent):
    """Agente que devuelve un AgentOutput fijo."""

    def __init__(self, output: AgentOutput):
        self._output_data = output
        self.name = output.agent
        self.category = "test"

    def analyze(self, context: AgentContext) -> AgentOutput:
        return self._output_data


def _make_output(
    agent: str = "test-agent",
    risk_score: int = 50,
    confidence: float = 0.9,
    status: AgentRunStatus = AgentRunStatus.COMPLETED,
    findings: list[Finding] | None = None,
    missing: list[str] | None = None,
) -> AgentOutput:
    return AgentOutput(
        agent=agent,
        status=status,
        risk_score=risk_score,
        confidence=confidence,
        summary=f"{agent} result",
        findings=findings or [],
        missing_information=missing or [],
    )


# =============================================================================
# Tolerancia a fallos
# =============================================================================


class TestOrchestratorFaults:
    """Un agente que eleva -> is_partial True, los demás siguen."""

    def test_agente_eleva_exception_is_partial(self):
        """Un agente que falla marca el caso como parcial."""
        ctx = make_context(signals={"jira": jira_signal()})
        orch = RiskOrchestrator(agents=[JiraAgent(), FailingAgent()])
        case = orch.analyze(ctx)
        assert case.is_partial is True

    def test_agentes_demas_siguen(self):
        """Los otros agentes producen su salida normalmente."""
        ctx = make_context(signals={"jira": jira_signal()})
        orch = RiskOrchestrator(agents=[JiraAgent(), FailingAgent()])
        outputs, _ = orch.run_agents(ctx)
        # Solo JiraAgent produce output (FailingAgent eleva)
        assert len(outputs) == 1
        assert outputs[0].agent == "jira-agent"

    def test_agente_skipped_no_is_partial(self):
        """Un agente SKIPPED NO marca el caso como parcial."""
        ctx = make_context(signals={})  # Ningún provider -> todos SKIPPED
        orch = RiskOrchestrator(agents=[JiraAgent(), CodeAgent()])
        case = orch.analyze(ctx)
        assert case.is_partial is False


# =============================================================================
# consolidate_score
# =============================================================================


class TestConsolidateScore:
    """La puntuación consolidada respeta pesos y corroboración."""

    def test_respeta_agent_weights(self):
        """Cálculo a mano: jira=90 (w=0.35), finance=70 (w=0.30)."""
        outputs = [
            _make_output("jira-agent", risk_score=90),
            _make_output("finance-agent", risk_score=70),
        ]
        total_w = AGENT_WEIGHTS["jira-agent"] + AGENT_WEIGHTS["finance-agent"]
        weighted = 90 * AGENT_WEIGHTS["jira-agent"] + 70 * AGENT_WEIGHTS["finance-agent"]
        base = weighted / total_w
        # Corroboración: 2 agentes >= 60 -> bonus de 5
        bonus = CORROBORATION_BONUS_PER_AGENT
        expected = int(min(round(base) + bonus, 100))
        assert RiskOrchestrator.consolidate_score(outputs) == expected

    def test_skipped_excluidos_del_promedio(self):
        """Agentes SKIPPED no cuentan como cero."""
        outputs = [
            _make_output("jira-agent", risk_score=80),
            _make_output("code-agent", status=AgentRunStatus.SKIPPED, risk_score=0),
        ]
        score = RiskOrchestrator.consolidate_score(outputs)
        # Sin el SKIPPED, es solo jira con 80 + bonus 0 (solo 1 agente >= 60)
        assert score == 80

    def test_todos_skipped_score_cero(self):
        outputs = [
            _make_output("jira-agent", status=AgentRunStatus.SKIPPED, risk_score=0),
            _make_output("code-agent", status=AgentRunStatus.SKIPPED, risk_score=0),
        ]
        assert RiskOrchestrator.consolidate_score(outputs) == 0

    def test_corroboracion_dos_agentes(self):
        """2 agentes >= CORROBORATION_THRESHOLD -> suma bonus."""
        outputs = [
            _make_output("jira-agent", risk_score=CORROBORATION_THRESHOLD),
            _make_output("code-agent", risk_score=CORROBORATION_THRESHOLD),
        ]
        # Base = media ponderada de 60 y 60 con pesos distintos = 60
        # Bonus = (2-1) * 5 = 5
        score = RiskOrchestrator.consolidate_score(outputs)
        assert score > CORROBORATION_THRESHOLD

    def test_un_solo_agente_alto_no_bonus(self):
        """Solo 1 agente >= umbral -> sin bonus."""
        outputs = [
            _make_output("jira-agent", risk_score=CORROBORATION_THRESHOLD),
            _make_output("code-agent", risk_score=CORROBORATION_THRESHOLD - 1),
        ]
        total_w = AGENT_WEIGHTS["jira-agent"] + AGENT_WEIGHTS["code-agent"]
        weighted = (
            CORROBORATION_THRESHOLD * AGENT_WEIGHTS["jira-agent"]
            + (CORROBORATION_THRESHOLD - 1) * AGENT_WEIGHTS["code-agent"]
        )
        expected = int(round(weighted / total_w))
        assert RiskOrchestrator.consolidate_score(outputs) == expected

    def test_tope_max_corroboration_bonus(self):
        """Bonus no pasa de MAX_CORROBORATION_BONUS."""
        outputs = [
            _make_output("jira-agent", risk_score=90),
            _make_output("code-agent", risk_score=80),
            _make_output("finance-agent", risk_score=70),
            _make_output("database-agent", risk_score=65),
        ]
        score = RiskOrchestrator.consolidate_score(outputs)
        # 4 agentes altos -> bonus = min((4-1)*5, 15) = 15
        # Verificar que no se excedió
        total_w = sum(AGENT_WEIGHTS[o.agent] for o in outputs)
        weighted = sum(o.risk_score * AGENT_WEIGHTS[o.agent] for o in outputs)
        base = round(weighted / total_w)
        assert score == min(base + MAX_CORROBORATION_BONUS, 100)

    def test_score_nunca_pasa_de_100(self):
        """Score tope es 100."""
        outputs = [
            _make_output("jira-agent", risk_score=100),
            _make_output("code-agent", risk_score=100),
            _make_output("finance-agent", risk_score=100),
            _make_output("database-agent", risk_score=100),
        ]
        assert RiskOrchestrator.consolidate_score(outputs) <= 100


# =============================================================================
# consolidate_confidence
# =============================================================================


class TestConsolidateConfidence:
    """Confianza penalizada por cobertura."""

    def test_penaliza_por_cobertura(self):
        """2 de 4 agentes -> confianza * 0.5."""
        outputs = [
            _make_output("jira-agent", confidence=1.0),
            _make_output("code-agent", confidence=1.0),
            _make_output("finance-agent", status=AgentRunStatus.SKIPPED, confidence=0.0),
            _make_output("database-agent", status=AgentRunStatus.SKIPPED, confidence=0.0),
        ]
        conf = RiskOrchestrator.consolidate_confidence(outputs)
        # mean=1.0, coverage=2/4=0.5 -> 1.0 * 0.5 = 0.5
        assert conf == 0.5

    def test_todos_skipped_confidence_cero(self):
        outputs = [
            _make_output("jira-agent", status=AgentRunStatus.SKIPPED),
            _make_output("code-agent", status=AgentRunStatus.SKIPPED),
        ]
        assert RiskOrchestrator.consolidate_confidence(outputs) == 0.0

    def test_cobertura_completa(self):
        """4/4 agentes contribuyen -> sin penalización."""
        outputs = [
            _make_output("jira-agent", confidence=0.8),
            _make_output("code-agent", confidence=0.9),
            _make_output("finance-agent", confidence=1.0),
            _make_output("database-agent", confidence=0.7),
        ]
        conf = RiskOrchestrator.consolidate_confidence(outputs)
        mean = (0.8 + 0.9 + 1.0 + 0.7) / 4
        assert conf == round(mean * 1.0, 2)


# =============================================================================
# classify_claims
# =============================================================================


class TestClassifyClaims:
    """Separa facts (conf=1.0), inferences (<1.0), assumptions siempre presentes."""

    def test_confidence_1_es_fact(self):
        f = Finding(
            category="schedule", code="overdue", severity=Severity.HIGH,
            risk_score=90, confidence=1.0, summary="Vencido"
        )
        out = _make_output("jira-agent", findings=[f])
        facts, inferences, _ = RiskOrchestrator.classify_claims([out])
        assert any("Vencido" in fact for fact in facts)

    def test_confidence_menor_es_inference(self):
        f = Finding(
            category="technical", code="large_diff", severity=Severity.MEDIUM,
            risk_score=45, confidence=0.7, summary="Diff grande"
        )
        out = _make_output("code-agent", findings=[f])
        facts, inferences, _ = RiskOrchestrator.classify_claims([out])
        assert any("Diff grande" in inf for inf in inferences)
        assert not any("Diff grande" in fact for fact in facts)

    def test_assumptions_siempre_presentes(self):
        """Las assumptions se declaran siempre, incluso sin findings."""
        facts, inferences, assumptions = RiskOrchestrator.classify_claims([])
        assert len(assumptions) > 0


# =============================================================================
# collect_missing
# =============================================================================


class TestCollectMissing:
    """No duplica entradas."""

    def test_no_duplica(self):
        out1 = _make_output("jira-agent", missing=["Sin datos de Jira"])
        out2 = _make_output("code-agent", missing=["Sin datos de Jira", "Sin coverage"])
        result = RiskOrchestrator.collect_missing([out1, out2])
        assert result.count("Sin datos de Jira") == 1
        assert "Sin coverage" in result


# =============================================================================
# build_causal_chain
# =============================================================================


class TestBuildCausalChain:
    """Orden: causa(code/db) -> efecto(jira) -> consecuencia(finance)."""

    def _make_outputs_with_findings(self):
        """Outputs con findings para cada agente."""
        code_f = Finding(
            category="technical", code="failing_checks", severity=Severity.CRITICAL,
            risk_score=85, confidence=1.0, summary="Checks fallando"
        )
        db_f = Finding(
            category="data", code="missing_rls", severity=Severity.CRITICAL,
            risk_score=90, confidence=1.0, summary="RLS ausente"
        )
        jira_f = Finding(
            category="schedule", code="overdue", severity=Severity.CRITICAL,
            risk_score=90, confidence=1.0, summary="Issue vencido"
        )
        finance_f = Finding(
            category="financial", code="penalty_exposure", severity=Severity.HIGH,
            risk_score=70, confidence=0.85, summary="Penalización activa"
        )
        return [
            _make_output("code-agent", risk_score=85, findings=[code_f]),
            _make_output("database-agent", risk_score=90, findings=[db_f]),
            _make_output("jira-agent", risk_score=90, findings=[jira_f]),
            _make_output("finance-agent", risk_score=70, findings=[finance_f]),
        ]

    def test_steps_numerados_desde_1_sin_huecos(self):
        outputs = self._make_outputs_with_findings()
        orch = RiskOrchestrator(agents=[])
        chain = orch.build_causal_chain(outputs)
        steps = [s.step for s in chain]
        assert steps == list(range(1, len(chain) + 1))

    def test_orden_causa_efecto_consecuencia(self):
        """code/db primero, jira después, finance al final."""
        outputs = self._make_outputs_with_findings()
        orch = RiskOrchestrator(agents=[])
        chain = orch.build_causal_chain(outputs)
        # Al menos 3 pasos
        assert len(chain) >= 3
        # Primer paso viene de code o db
        assert "Checks" in chain[0].cause or "RLS" in chain[0].cause
        # Último paso menciona consecuencia financiera
        last = chain[-1]
        assert "contractual" in last.cause.lower() or "penalización" in last.effect.lower() or "Penalización" in last.effect


# =============================================================================
# build_premortem
# =============================================================================


class TestBuildPremortem:
    """Pre-mortem menciona título del commitment; modos vienen de findings >= 60."""

    def test_assumed_failure_menciona_titulo(self):
        ctx = make_context(signals={"jira": jira_signal()})
        orch = RiskOrchestrator(agents=[JiraAgent()])
        case = orch.analyze(ctx)
        assert ctx.commitment.title in case.premortem.assumed_failure

    def test_failure_modes_from_high_findings(self):
        """Solo findings con risk_score >= CORROBORATION_THRESHOLD -> modos."""
        f_high = Finding(
            category="schedule", code="overdue", severity=Severity.CRITICAL,
            risk_score=90, confidence=1.0, summary="Vencido"
        )
        f_low = Finding(
            category="schedule", code="stale", severity=Severity.MEDIUM,
            risk_score=50, confidence=1.0, summary="Estancado"
        )
        out = _make_output("jira-agent", risk_score=90, findings=[f_high, f_low])
        premortem = RiskOrchestrator.build_premortem(
            make_context(signals={"jira": jira_signal()}), [out]
        )
        mode_texts = " ".join(premortem.failure_modes)
        assert "Vencido" in mode_texts
        assert "Estancado" not in mode_texts


# =============================================================================
# build_scenarios
# =============================================================================


class TestBuildScenarios:
    """SIEMPRE 3 escenarios, uno por ScenarioKind, en orden."""

    def _run_scenarios(self, score: int = 80) -> list[Scenario]:
        ctx = make_context(
            signals={"jira": jira_signal()},
            commitment_kw={"financial_exposure": Decimal("20000")},
        )
        outputs = [_make_output("jira-agent", risk_score=score)]
        orch = RiskOrchestrator(agents=[])
        return orch.build_scenarios(ctx, outputs, score)

    def test_siempre_exactamente_3(self):
        scenarios = self._run_scenarios()
        assert len(scenarios) == 3

    def test_uno_de_cada_kind(self):
        scenarios = self._run_scenarios()
        kinds = [s.kind for s in scenarios]
        assert kinds == [
            ScenarioKind.DO_NOTHING,
            ScenarioKind.ADD_CAPACITY,
            ScenarioKind.RENEGOTIATE_SCOPE,
        ]

    def test_do_nothing_expected_cost(self):
        """do_nothing.expected_cost = exposure * (score/100) redondeado a 2 decimales."""
        score = 80
        exposure = Decimal("20000")
        scenarios = self._run_scenarios(score)
        do_nothing = scenarios[0]
        expected = (exposure * Decimal(str(score)) / Decimal("100")).quantize(Decimal("0.01"))
        assert do_nothing.expected_cost == expected

    def test_residual_exposure_decrece(self):
        """do_nothing > add_capacity > renegotiate_scope."""
        scenarios = self._run_scenarios()
        assert scenarios[0].residual_exposure > scenarios[1].residual_exposure
        assert scenarios[1].residual_exposure > scenarios[2].residual_exposure

    def test_sin_datos_coste_none(self):
        """Sin hourly_cost ni effort -> expected_cost de add_capacity es None."""
        ctx = make_context(
            signals={"jira": jira_signal()},
            project=make_project(hourly_cost=Decimal("0")),
            commitment_kw={"financial_exposure": Decimal("20000")},
        )
        # Output sin recommended_actions (sin estimated_effort_hours)
        outputs = [_make_output("jira-agent", risk_score=80)]
        orch = RiskOrchestrator(agents=[])
        scenarios = orch.build_scenarios(ctx, outputs, 80)
        add_cap = scenarios[1]
        assert add_cap.expected_cost is None

    def test_renegotiate_cost_none(self):
        """renegotiate_scope.expected_cost siempre None."""
        scenarios = self._run_scenarios()
        assert scenarios[2].expected_cost is None


# =============================================================================
# Caso demo reproducible
# =============================================================================


class TestCasoDemoReproducible:
    """Con las señales del caso obligatorio el score es >= 80 y severity CRITICAL.

    Señales:
    - Jira: DAT-42 blocked, unassigned, overdue
    - GitHub: PR abierto + checks fallidos + coverage 41 + migración DROP sin rollback
    - Supabase: tabla payments sin RLS
    """

    def test_caso_demo(self):
        """El caso demo produce score >= 80 y severity CRITICAL."""
        commitment = make_commitment(
            title="Entregar integración de pagos empresariales antes del viernes",
            due_date=NOW - timedelta(days=1),  # overdue
            financial_exposure=Decimal("20000"),
        )

        jira_sig = jira_signal(
            issue_key="DAT-42",
            status="Blocked",
            assignee=None,
        )

        pr = make_open_pr(
            number=7,
            mergeable=True,
            approved_reviews=0,
            created_at=(NOW - timedelta(days=4)).isoformat(),
            additions=200,
            deletions=50,
        )
        checks = [
            {"name": "ci-tests", "conclusion": "failure"},
            {"name": "ci-lint", "conclusion": "failure"},
        ]
        migration = {
            "path": "supabase/migrations/20260725_payments.sql",
            "content": "DROP TABLE old_payments; ALTER COLUMN amount;",
            "has_rollback": False,
        }
        gh_sig = github_signal(
            pull_requests=[pr],
            checks=checks,
            changed_files=["src/payments.py", "src/gateway.py"],
            coverage=41,
            migrations=[migration],
        )

        payments_table = make_table(
            name="payments",
            rls_enabled=False,
        )
        sb_sig = supabase_signal(tables=[payments_table])

        fin_sig = finance_signal()  # Usa el seed

        ctx = make_context(
            signals={
                "jira": jira_sig,
                "github": gh_sig,
                "supabase": sb_sig,
                "finance": fin_sig,
            },
            commitment=commitment,
        )

        orch = RiskOrchestrator()
        case = orch.analyze(ctx)

        assert case.consolidated_score >= 80, f"Score {case.consolidated_score} < 80"
        assert case.severity == Severity.CRITICAL
        assert case.is_partial is False
        # Cadena causal presente
        assert len(case.causal_chain) >= 2
        # Pre-mortem menciona el título
        assert commitment.title in case.premortem.assumed_failure
        # Siempre 3 escenarios
        assert len(case.scenarios) == 3


class TestCasoDemoEscenarios:
    """Verifica propiedades de los escenarios del caso demo."""

    @pytest.fixture
    def demo_case(self) -> RiskCase:
        commitment = make_commitment(
            title="Entregar integración de pagos empresariales antes del viernes",
            due_date=NOW - timedelta(days=1),
            financial_exposure=Decimal("20000"),
        )
        ctx = make_context(
            signals={
                "jira": jira_signal(issue_key="DAT-42", status="Blocked", assignee=None),
                "github": github_signal(
                    pull_requests=[make_open_pr(approved_reviews=0, created_at=(NOW - timedelta(days=4)).isoformat())],
                    checks=[{"name": "ci", "conclusion": "failure"}],
                    changed_files=["src/x.py"],
                    coverage=41,
                    migrations=[{"path": "m.sql", "content": "DROP TABLE x;", "has_rollback": False}],
                ),
                "supabase": supabase_signal(tables=[make_table(name="payments", rls_enabled=False)]),
                "finance": finance_signal(),
            },
            commitment=commitment,
        )
        return RiskOrchestrator().analyze(ctx)

    def test_do_nothing_exposure_full(self, demo_case: RiskCase):
        """do_nothing.residual_exposure = exposure total."""
        do_nothing = demo_case.scenarios[0]
        assert do_nothing.residual_exposure == Decimal("20000")

    def test_kinds_en_orden(self, demo_case: RiskCase):
        kinds = [s.kind for s in demo_case.scenarios]
        assert kinds == [
            ScenarioKind.DO_NOTHING,
            ScenarioKind.ADD_CAPACITY,
            ScenarioKind.RENEGOTIATE_SCOPE,
        ]
