"""Tests de los agentes (RF-8).

Es la capa más valiosa de probar y la más barata: los agentes son puros, así que cada test es una
entrada y una salida, sin red ni base de datos.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.agents.base import Agent, AgentContext, BaseAgent
from app.agents.commitment_agent import CommitmentAgent
from app.agents.financial_agent import DEFAULT_ESTIMATED_HOURS, FinancialAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.risk_agent import DIMENSION_WEIGHTS, RiskAgent
from app.agents.technical_agent import STALE_DAYS, TechnicalAgent
from app.schemas.analysis import (
    AgentOutcome,
    CommitmentStatus,
    ProjectSnapshot,
    Severity,
    Signal,
    severity_for_score,
)
from app.schemas.events import EventKind, ProviderName
from app.tests.factories import (
    NOW,
    make_commitment,
    make_context,
    make_event,
    status_change,
)


def codes(outcome: AgentOutcome) -> set[str]:
    return set(outcome.codes)


class TestPurity:
    """RF-8.3 y RF-8.4: ningún agente conoce el framework ni el almacenamiento."""

    @pytest.mark.parametrize(
        "module_name",
        [
            "app.agents.base",
            "app.agents.commitment_agent",
            "app.agents.technical_agent",
            "app.agents.financial_agent",
            "app.agents.risk_agent",
            "app.agents.orchestrator",
        ],
    )
    def test_agents_do_not_import_fastapi_or_supabase(self, module_name: str) -> None:
        import inspect
        from importlib import import_module

        source = inspect.getsource(import_module(module_name))

        assert "fastapi" not in source
        assert "supabase" not in source
        assert "repositor" not in source.lower()

    def test_agents_do_not_branch_on_provider(self) -> None:
        """Un ``if provider == "jira"`` sería la señal de que el desacople falló.

        Se comprueba sobre el árbol sintáctico y no sobre el texto: los docstrings mencionan a
        Jira y GitHub como ejemplos de correspondencia, y eso es documentación, no acoplamiento.
        Lo que no puede aparecer es un nombre de provider en una constante del código.
        """
        import ast
        import inspect
        from importlib import import_module

        provider_names = {name.value for name in ProviderName}

        for module_name in (
            "app.agents.commitment_agent",
            "app.agents.technical_agent",
            "app.agents.financial_agent",
            "app.agents.risk_agent",
        ):
            source = inspect.getsource(import_module(module_name))
            tree = ast.parse(source)

            docstrings = {
                text
                for node in ast.walk(tree)
                if isinstance(
                    node,
                    ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
                )
                for text in [ast.get_docstring(node, clean=False)]
                if text
            }
            code_literals = {
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            } - docstrings

            offenders = {
                literal
                for literal in code_literals
                if literal.strip().lower() in provider_names
            }
            assert not offenders, f"{module_name} ramifica por provider: {offenders}"
            assert "ProviderName" not in source

    @pytest.mark.parametrize(
        "agent",
        [CommitmentAgent(), TechnicalAgent(), FinancialAgent(), RiskAgent()],
    )
    def test_agents_satisfy_the_protocol(self, agent: Agent) -> None:
        assert isinstance(agent, Agent)

    @pytest.mark.parametrize(
        "agent",
        [CommitmentAgent(), TechnicalAgent(), FinancialAgent()],
    )
    def test_same_input_yields_same_output(self, agent: Agent) -> None:
        """RF-8.7: determinismo."""
        context = make_context()

        assert agent.run(context) == agent.run(context)

    def test_provider_agnostic_event_is_analysed_the_same(self) -> None:
        """El mismo escenario desde GitHub produce el mismo resultado."""
        jira = make_context(
            event=make_event(provider=ProviderName.JIRA, due_date=NOW - timedelta(days=5))
        )
        github = make_context(
            event=make_event(
                provider=ProviderName.GITHUB,
                external_key="org/repo#17",
                due_date=NOW - timedelta(days=5),
            )
        )
        agent = CommitmentAgent()

        assert agent.run(jira).score == agent.run(github).score


class TestCommitmentAgent:
    def test_overdue_is_detected(self) -> None:
        context = make_context(event=make_event(due_date=NOW - timedelta(days=4)))

        outcome = CommitmentAgent().run(context)

        assert "overdue" in codes(outcome)
        assert outcome.score >= 80

    def test_due_soon_is_detected(self) -> None:
        context = make_context(event=make_event(due_date=NOW + timedelta(days=2)))

        assert "due_soon" in codes(CommitmentAgent().run(context))

    def test_due_approaching_is_milder(self) -> None:
        soon = make_context(event=make_event(due_date=NOW + timedelta(days=2)))
        approaching = make_context(event=make_event(due_date=NOW + timedelta(days=6)))
        agent = CommitmentAgent()

        assert agent.run(approaching).score < agent.run(soon).score

    def test_distant_due_date_raises_no_signal(self) -> None:
        context = make_context(event=make_event(due_date=NOW + timedelta(days=60)))

        assert CommitmentAgent().run(context).signals == []

    def test_missing_due_date_is_itself_a_risk(self) -> None:
        """Sin fecha no hay compromiso medible."""
        context = make_context(event=make_event(due_date=None))

        assert "missing_due_date" in codes(CommitmentAgent().run(context))

    def test_breached_commitment_scores_highest(self) -> None:
        context = make_context(
            commitment=make_commitment(status=CommitmentStatus.BREACHED)
        )

        outcome = CommitmentAgent().run(context)

        assert "commitment_breached" in codes(outcome)
        assert outcome.score >= 90

    def test_met_commitment_contributes_no_risk(self) -> None:
        """Un compromiso cumplido no debe arrastrar señales del resto."""
        context = make_context(
            event=make_event(due_date=NOW - timedelta(days=10)),
            commitment=make_commitment(
                status=CommitmentStatus.MET, due_date=NOW - timedelta(days=10)
            ),
        )

        outcome = CommitmentAgent().run(context)

        assert outcome.score == 0
        assert outcome.detail["closed"] is True

    def test_reopening_is_detected_from_the_changelog(self) -> None:
        """Un elemento reabierto y vuelto a cerrar solo deja rastro en el histórico."""
        context = make_context(
            event=make_event(changes=[status_change("Done", "In Progress")])
        )

        assert "reopened" in codes(CommitmentAgent().run(context))

    def test_normal_progress_is_not_a_reopening(self) -> None:
        context = make_context(
            event=make_event(changes=[status_change("To Do", "In Progress")])
        )

        assert "reopened" not in codes(CommitmentAgent().run(context))

    def test_commitment_due_date_wins_over_event(self) -> None:
        """El compromiso registrado es la fuente de verdad de la fecha."""
        context = make_context(
            event=make_event(due_date=NOW + timedelta(days=60)),
            commitment=make_commitment(due_date=NOW - timedelta(days=1)),
        )

        assert "overdue" in codes(CommitmentAgent().run(context))


class TestTechnicalAgent:
    @pytest.mark.parametrize("marker", ["Blocked", "bloqueado", "On Hold"])
    def test_blocked_state_is_detected(self, marker: str) -> None:
        context = make_context(event=make_event(state=marker))

        assert "blocked" in codes(TechnicalAgent().run(context))

    def test_blocked_label_is_detected(self) -> None:
        context = make_context(event=make_event(labels=["impedimento"]))

        assert "blocked" in codes(TechnicalAgent().run(context))

    def test_unassigned_work_is_flagged(self) -> None:
        context = make_context(event=make_event(owner=None))

        assert "unassigned" in codes(TechnicalAgent().run(context))

    def test_stale_work_is_flagged(self) -> None:
        context = make_context(
            event=make_event(occurred_at=NOW - timedelta(days=STALE_DAYS + 1))
        )

        assert "stale" in codes(TechnicalAgent().run(context))

    def test_recent_work_is_not_stale(self) -> None:
        context = make_context(event=make_event(occurred_at=NOW - timedelta(hours=2)))

        assert "stale" not in codes(TechnicalAgent().run(context))

    def test_future_timestamp_does_not_produce_negative_staleness(self) -> None:
        """Solo puede ser un desajuste de reloj; no debe inventar antigüedad."""
        context = make_context(event=make_event(occurred_at=NOW + timedelta(days=1)))

        outcome = TechnicalAgent().run(context)

        assert outcome.detail["stale_days"] is None
        assert "stale" not in codes(outcome)

    def test_ownership_churn_is_counted_across_history(self) -> None:
        from app.schemas.events import FieldChange

        change = FieldChange(field="assignee", from_value="Ada", to_value="Grace")
        context = make_context(
            event=make_event(changes=[change]),
            recent_events=[make_event(changes=[change])],
        )

        outcome = TechnicalAgent().run(context)

        assert "ownership_churn" in codes(outcome)
        assert outcome.detail["reassignments"] == 2

    def test_review_without_reviewer_is_flagged(self) -> None:
        """Regla que solo tiene sentido para un provider con revisiones."""
        context = make_context(
            event=make_event(
                provider=ProviderName.GITHUB,
                kind=EventKind.REVIEW_REQUESTED,
                owner=None,
            )
        )

        assert "review_without_reviewer" in codes(TechnicalAgent().run(context))

    def test_healthy_work_produces_no_signals(self) -> None:
        context = make_context(event=make_event(occurred_at=NOW))

        assert TechnicalAgent().run(context).signals == []


class TestFinancialAgent:
    def test_impact_is_hours_by_cost(self) -> None:
        context = make_context(
            event=make_event(estimated_hours=10.0, due_date=NOW + timedelta(days=10)),
            project=ProjectSnapshot(jira_project_key="DEMO", hourly_cost=100.0),
        )

        outcome = FinancialAgent().run(context)

        assert outcome.detail["financial_impact"] == 1000.0

    def test_overdue_work_multiplies_the_impact(self) -> None:
        on_time = make_context(
            event=make_event(estimated_hours=10.0, due_date=NOW + timedelta(days=5)),
            project=ProjectSnapshot(jira_project_key="DEMO", hourly_cost=100.0),
        )
        late = make_context(
            event=make_event(estimated_hours=10.0, due_date=NOW - timedelta(days=20)),
            project=ProjectSnapshot(jira_project_key="DEMO", hourly_cost=100.0),
        )
        agent = FinancialAgent()

        assert (
            agent.run(late).detail["financial_impact"]
            > agent.run(on_time).detail["financial_impact"]
        )

    def test_missing_hourly_cost_is_reported_not_silently_zero(self) -> None:
        """Sin coste por hora las alertas pierden su mejor argumento; hay que decirlo."""
        context = make_context(
            project=ProjectSnapshot(jira_project_key="DEMO", hourly_cost=0.0)
        )

        outcome = FinancialAgent().run(context)

        assert "missing_hourly_cost" in codes(outcome)
        assert outcome.detail["financial_impact"] == 0.0

    def test_absent_estimate_falls_back_and_declares_it(self) -> None:
        context = make_context(event=make_event(estimated_hours=None))

        outcome = FinancialAgent().run(context)

        assert outcome.detail["hours_at_risk"] == DEFAULT_ESTIMATED_HOURS
        assert outcome.detail["hours_were_estimated"] is True

    def test_commitment_estimate_wins_over_event(self) -> None:
        context = make_context(
            event=make_event(estimated_hours=1.0),
            commitment=make_commitment(estimated_hours=40.0),
        )

        assert FinancialAgent().run(context).detail["hours_at_risk"] == 40.0

    def test_larger_exposure_weighs_more(self) -> None:
        small = make_context(
            event=make_event(estimated_hours=1.0, due_date=NOW + timedelta(days=10)),
            project=ProjectSnapshot(jira_project_key="DEMO", hourly_cost=10.0),
        )
        large = make_context(
            event=make_event(estimated_hours=200.0, due_date=NOW + timedelta(days=10)),
            project=ProjectSnapshot(jira_project_key="DEMO", hourly_cost=200.0),
        )
        agent = FinancialAgent()

        assert agent.run(large).score > agent.run(small).score

    def test_impact_is_never_negative(self) -> None:
        context = make_context(
            event=make_event(estimated_hours=0.0, due_date=NOW + timedelta(days=1))
        )

        assert FinancialAgent().run(context).detail["financial_impact"] >= 0


class TestRiskAgent:
    def test_weights_sum_to_one(self) -> None:
        """Mantiene la escala 0–100 sin normalizaciones sorpresa."""
        assert sum(DIMENSION_WEIGHTS.values()) == pytest.approx(1.0)

    def test_score_is_a_weighted_combination(self) -> None:
        outcomes = [
            AgentOutcome(agent="commitment", score=100),
            AgentOutcome(agent="technical", score=0),
            AgentOutcome(agent="financial", score=0),
        ]

        score, _ = RiskAgent().score(outcomes)

        assert score == pytest.approx(45, abs=1)

    def test_missing_dimension_redistributes_its_weight(self) -> None:
        """Un análisis parcial no debe parecer menos grave por faltar información."""
        score, _ = RiskAgent().score([AgentOutcome(agent="commitment", score=80)])

        assert score == 80

    def test_no_outcomes_is_zero(self) -> None:
        score, severity = RiskAgent().score([])

        assert score == 0
        assert severity is Severity.LOW

    def test_critical_signal_imposes_a_floor(self) -> None:
        """Un hallazgo grave en una sola dimensión no debe diluirse."""
        outcomes = [
            AgentOutcome(
                agent="commitment",
                score=95,
                signals=[Signal(code="breached", message="x", weight=95)],
            ),
            AgentOutcome(agent="technical", score=0),
            AgentOutcome(agent="financial", score=0),
        ]

        score, severity = RiskAgent().score(outcomes)

        assert score >= 70
        assert severity in {Severity.HIGH, Severity.CRITICAL}

    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0, Severity.LOW),
            (39, Severity.LOW),
            (40, Severity.MEDIUM),
            (59, Severity.MEDIUM),
            (60, Severity.HIGH),
            (79, Severity.HIGH),
            (80, Severity.CRITICAL),
            (100, Severity.CRITICAL),
        ],
    )
    def test_severity_bands(self, score: int, expected: Severity) -> None:
        assert severity_for_score(score) is expected

    def test_dominant_signal_is_the_heaviest(self) -> None:
        outcomes = [
            AgentOutcome(
                agent="commitment",
                score=50,
                signals=[Signal(code="leve", message="x", weight=10)],
            ),
            AgentOutcome(
                agent="technical",
                score=80,
                signals=[Signal(code="grave", message="y", weight=90)],
            ),
        ]

        dominant = RiskAgent().dominant_signal(outcomes)

        assert dominant is not None
        assert dominant.code == "grave"

    def test_ties_are_broken_deterministically(self) -> None:
        """El motivo identifica la alerta abierta: un empate no puede variar entre ejecuciones."""
        outcomes = [
            AgentOutcome(
                agent="technical",
                score=50,
                signals=[
                    Signal(code="zeta", message="x", weight=50),
                    Signal(code="alfa", message="y", weight=50),
                ],
            )
        ]
        agent = RiskAgent()

        assert agent.dominant_signal(outcomes) == agent.dominant_signal(outcomes)

    def test_no_signals_yields_no_dominant(self) -> None:
        assert RiskAgent().dominant_signal([]) is None


class TestScoreComposition:
    def test_agent_score_is_the_maximum_not_the_sum(self) -> None:
        """Sumar haría que tres señales leves pesaran más que una grave."""

        class ThreeMild(BaseAgent):
            name = "mild"

            def run(self, context: AgentContext) -> AgentOutcome:
                return self._outcome(
                    [
                        Signal(code="a", message="x", weight=20),
                        Signal(code="b", message="y", weight=20),
                        Signal(code="c", message="z", weight=20),
                    ]
                )

        assert ThreeMild().run(make_context()).score == 20

    def test_score_is_capped_at_100(self) -> None:
        class Extreme(BaseAgent):
            name = "extreme"

            def run(self, context: AgentContext) -> AgentOutcome:
                return self._outcome([Signal(code="a", message="x", weight=100)])

        assert Extreme().run(make_context()).score == 100


class TestOrchestratorAgent:
    def test_healthy_scenario_scores_low(self) -> None:
        result = OrchestratorAgent().analyse(make_context())

        assert result.severity is Severity.LOW
        assert result.is_partial is False

    def test_critical_scenario_scores_high(self) -> None:
        context = make_context(
            event=make_event(
                state="Blocked",
                owner=None,
                due_date=NOW - timedelta(days=10),
                estimated_hours=40.0,
            ),
            project=ProjectSnapshot(jira_project_key="DEMO", hourly_cost=80.0),
        )

        result = OrchestratorAgent().analyse(context)

        assert result.risk_score >= 80
        assert result.severity is Severity.CRITICAL
        assert result.primary_reason == "overdue"

    def test_every_agent_contributes_an_outcome(self) -> None:
        result = OrchestratorAgent().analyse(make_context())

        assert {outcome.agent for outcome in result.outcomes} == {
            "commitment",
            "technical",
            "financial",
        }

    def test_failing_agent_yields_a_partial_analysis(self) -> None:
        """RF-8.6: se pierde una dimensión, no el análisis."""

        class Broken:
            name = "technical"

            def run(self, context: AgentContext) -> AgentOutcome:
                raise RuntimeError("boom")

        result = OrchestratorAgent(agents=[CommitmentAgent(), Broken()]).analyse(
            make_context()
        )

        assert result.is_partial is True
        assert [outcome.agent for outcome in result.outcomes] == ["commitment"]

    def test_all_agents_failing_still_returns_a_result(self) -> None:
        class Broken:
            name = "broken"

            def run(self, context: AgentContext) -> AgentOutcome:
                raise RuntimeError("boom")

        result = OrchestratorAgent(agents=[Broken()]).analyse(make_context())

        assert result.is_partial is True
        assert result.risk_score == 0

    def test_financial_impact_comes_from_the_financial_agent(self) -> None:
        """La fórmula vive en un solo sitio; duplicarla haría divergir las copias."""
        context = make_context(
            event=make_event(estimated_hours=10.0, due_date=NOW + timedelta(days=10)),
            project=ProjectSnapshot(jira_project_key="DEMO", hourly_cost=100.0),
        )

        result = OrchestratorAgent().analyse(context)

        assert result.financial_impact == 1000.0

    def test_impact_is_zero_without_the_financial_agent(self) -> None:
        result = OrchestratorAgent(agents=[CommitmentAgent()]).analyse(make_context())

        assert result.financial_impact == 0.0

    def test_findings_are_keyed_by_agent(self) -> None:
        """Es lo que se persiste en la columna ``findings``."""
        findings = OrchestratorAgent().analyse(make_context()).findings()

        assert set(findings) == {"commitment", "technical", "financial"}
        assert findings["commitment"]["agent"] == "commitment"

    def test_findings_are_json_serialisable(self) -> None:
        import json

        findings = OrchestratorAgent().analyse(make_context()).findings()

        assert json.dumps(findings)

    def test_agents_are_injectable(self) -> None:
        """Permite sustituir un agente determinístico por uno con LLM sin tocar la clase."""

        class Custom(BaseAgent):
            name = "commitment"

            def run(self, context: AgentContext) -> AgentOutcome:
                return self._outcome([Signal(code="custom", message="x", weight=100)])

        result = OrchestratorAgent(agents=[Custom()]).analyse(make_context())

        assert result.primary_reason == "custom"

    def test_orchestrator_satisfies_the_agent_protocol(self) -> None:
        assert isinstance(OrchestratorAgent(), Agent)

    def test_analysis_is_deterministic(self) -> None:
        context = make_context()
        agent = OrchestratorAgent()

        assert agent.analyse(context) == agent.analyse(context)
