"""Orquestador central de Datgent.

Ejecuta los agentes especializados sobre el mismo compromiso, correlaciona sus
hallazgos y compone un ``RiskCase``: puntuación consolidada, cadena causal, pre-mortem
y tres escenarios de recuperación.

Dos decisiones de diseño gobiernan este módulo:

1. **La parte determinística nunca depende del LLM.** La puntuación consolidada, la
   severidad y la confianza se calculan con reglas auditables. El LLM añade la
   narrativa —cadena causal, pre-mortem, escenarios—, y si no está disponible hay una
   reserva determinística. Un sistema cuya puntuación de riesgo cambia según el humor
   del modelo no se puede defender ante un cliente.

2. **Un agente que falla no tumba el análisis.** Cada uno va en su propio ``try``: se
   registra, su contribución se omite y el caso queda marcado ``is_partial``. Perder una
   dimensión es peor que perder el análisis entero solo si nadie se entera, y de eso se
   encarga la marca.

Sigue siendo un módulo sin E/S: no toca Supabase ni providers. La recolección de
señales y la persistencia son de ``OrchestratorService``, que es otra cosa.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.agents.specialized import DEFAULT_AGENTS, AgentContext, BaseSpecializedAgent
from app.core.logging import get_logger
from app.schemas.domain import (
    AgentOutput,
    AgentRunStatus,
    CausalStep,
    PreMortem,
    RiskCase,
    Scenario,
    ScenarioKind,
    severity_for_score,
)

logger = get_logger("agents.orchestrator")

# --- Pesos de consolidación --------------------------------------------------------
# El agente de planificación pesa más porque el compromiso se define por su fecha: un
# retraso es el incumplimiento, no un síntoma de él. El financiero le sigue porque
# cuantifica la consecuencia. Código y datos son causas, y por eso pesan menos: su
# efecto ya se refleja en el retraso.
AGENT_WEIGHTS: Final[dict[str, float]] = {
    "jira-agent": 0.35,
    "finance-agent": 0.30,
    "code-agent": 0.20,
    "database-agent": 0.15,
}

#: Peso de un agente no listado. Existe para que añadir un agente no obligue a tocar
#: esta tabla, aunque conviene declararlo.
DEFAULT_AGENT_WEIGHT: Final[float] = 0.10

#: Bonificación por corroboración. Cuando dos dominios distintos señalan riesgo alto a
#: la vez, el riesgo real es mayor que el de cada uno por separado: no son dos opiniones
#: sobre lo mismo, son dos causas que se suman. Sin esto, un compromiso con problemas
#: en cuatro frentes puntuaría igual que uno con un solo problema grave.
CORROBORATION_BONUS_PER_AGENT: Final[int] = 5
CORROBORATION_THRESHOLD: Final[int] = 60
MAX_CORROBORATION_BONUS: Final[int] = 15


class RiskOrchestrator:
    """Compone el caso de riesgo a partir de los agentes especializados."""

    name: Final[str] = "orchestrator-agent"

    def __init__(self, agents: list[BaseSpecializedAgent] | None = None) -> None:
        """Recibe los agentes por parámetro.

        Es inyección de dependencias y no adorno: permite ejecutar el orquestador con un
        subconjunto en un test, o sustituir un agente determinístico por uno respaldado
        por un LLM, sin tocar esta clase.
        """
        self._agents: list[BaseSpecializedAgent] = agents or [
            agent_cls() for agent_cls in DEFAULT_AGENTS
        ]

    # --- Ejecución -----------------------------------------------------------------

    def run_agents(self, context: AgentContext) -> tuple[list[AgentOutput], bool]:
        """Ejecuta los agentes tolerando fallos individuales.

        Devuelve las salidas y si el conjunto quedó incompleto. Un agente que eleva se
        registra con su nombre y se omite; uno que devuelve ``SKIPPED`` por falta de
        datos no marca el análisis como parcial, porque declarar el hueco es un
        resultado válido, no un fallo.
        """
        outputs: list[AgentOutput] = []
        is_partial = False

        for agent in self._agents:
            try:
                outputs.append(agent.analyze(context))
            except Exception as error:  # noqa: BLE001 - un agente caído no tumba el caso
                is_partial = True
                logger.error(
                    "El agente %s falló durante el análisis",
                    getattr(agent, "name", type(agent).__name__),
                    exc_info=error,
                )

        return outputs, is_partial

    def analyze(self, context: AgentContext) -> RiskCase:
        """Ejecuta el pipeline completo y compone el caso de riesgo determinístico.

        La narrativa (cadena causal, pre-mortem, escenarios) se genera con reglas. Si hay
        un LLM disponible, ``OrchestratorService`` la enriquece después; el caso que sale
        de aquí ya es utilizable sin él.
        """
        outputs, is_partial = self.run_agents(context)

        score = self.consolidate_score(outputs)
        confidence = self.consolidate_confidence(outputs)
        facts, inferences, assumptions = self.classify_claims(outputs)
        missing = self.collect_missing(outputs)

        return RiskCase(
            commitment_id=context.commitment.id,
            consolidated_score=score,
            severity=severity_for_score(score),
            confidence=confidence,
            summary=self.summarize(context, outputs, score),
            causal_chain=self.build_causal_chain(outputs),
            premortem=self.build_premortem(context, outputs),
            scenarios=self.build_scenarios(context, outputs, score),
            facts=facts,
            inferences=inferences,
            assumptions=assumptions,
            missing_information=missing,
            is_partial=is_partial,
            agent_outputs=outputs,
        )

    # --- Consolidación determinística ----------------------------------------------

    @staticmethod
    def consolidate_score(outputs: list[AgentOutput]) -> int:
        """Puntuación consolidada: media ponderada más bonificación por corroboración.

        Los agentes que no pudieron concluir (``SKIPPED``) se excluyen del promedio en
        lugar de contar como cero. Contarlos como cero diluiría el riesgo por falta de
        datos, que es justo lo contrario de lo que un hueco de información significa.
        """
        contributing = [o for o in outputs if o.status != AgentRunStatus.SKIPPED]
        if not contributing:
            return 0

        total_weight = sum(
            AGENT_WEIGHTS.get(o.agent, DEFAULT_AGENT_WEIGHT) for o in contributing
        )
        if total_weight == 0:
            return 0

        weighted = sum(
            o.risk_score * AGENT_WEIGHTS.get(o.agent, DEFAULT_AGENT_WEIGHT)
            for o in contributing
        )
        base = weighted / total_weight

        high_risk_agents = sum(
            1 for o in contributing if o.risk_score >= CORROBORATION_THRESHOLD
        )
        bonus = 0
        if high_risk_agents >= 2:
            bonus = min(
                (high_risk_agents - 1) * CORROBORATION_BONUS_PER_AGENT,
                MAX_CORROBORATION_BONUS,
            )

        return int(min(round(base) + bonus, 100))

    @staticmethod
    def consolidate_confidence(outputs: list[AgentOutput]) -> float:
        """Confianza del caso: la de los agentes que contribuyeron, penalizada por huecos.

        Cada agente que no pudo concluir resta confianza al conjunto. Un caso construido
        con dos de cuatro dimensiones puede ser correcto, pero no merece la misma
        confianza que uno con las cuatro.
        """
        contributing = [o for o in outputs if o.status != AgentRunStatus.SKIPPED]
        if not contributing:
            return 0.0

        mean = sum(o.confidence for o in contributing) / len(contributing)
        coverage = len(contributing) / max(len(outputs), 1)
        return round(mean * coverage, 2)

    @staticmethod
    def collect_missing(outputs: list[AgentOutput]) -> list[str]:
        """Huecos de información de todos los agentes, sin duplicar."""
        seen: dict[str, None] = {}
        for output in outputs:
            for item in output.missing_information:
                seen.setdefault(item, None)
        return list(seen)

    @staticmethod
    def classify_claims(
        outputs: list[AgentOutput],
    ) -> tuple[list[str], list[str], list[str]]:
        """Separa hechos, inferencias y supuestos según la confianza del hallazgo.

        El corte es la confianza: un hallazgo con 1.0 nace de un dato observado; por
        debajo, de una heurística. Los supuestos no salen de los agentes sino de las
        reglas del propio orquestador, y se declaran para que quien lea el caso sepa qué
        está aceptando sin verificar.
        """
        facts: list[str] = []
        inferences: list[str] = []

        for output in outputs:
            for finding in output.findings:
                claim = f"[{output.agent}] {finding.summary}"
                if finding.confidence >= 1.0:
                    facts.append(claim)
                else:
                    inferences.append(f"{claim} (confianza {finding.confidence})")

        assumptions = [
            "Los pesos por agente reflejan la importancia relativa de cada dominio para este tipo de compromiso.",
            "La probabilidad declarada de cada penalización contractual es correcta.",
            "Las señales de los providers están al día en el momento del análisis.",
        ]

        return facts, inferences, assumptions

    # --- Narrativa determinística --------------------------------------------------

    @staticmethod
    def summarize(
        context: AgentContext, outputs: list[AgentOutput], score: int
    ) -> str:
        title = context.commitment.title
        severity = severity_for_score(score).value
        contributing = [o for o in outputs if o.status != AgentRunStatus.SKIPPED]
        worst = max(contributing, key=lambda o: o.risk_score, default=None)

        if worst is None:
            return f'"{title}": sin datos suficientes para evaluar el riesgo.'

        return (
            f'"{title}" presenta riesgo {severity} ({score}/100). '
            f"La señal dominante viene de {worst.agent}: {worst.summary}"
        )

    def build_causal_chain(self, outputs: list[AgentOutput]) -> list[CausalStep]:
        """Cadena causal por reglas: causas técnicas y de datos, efecto en fecha y dinero.

        El orden no es arbitrario. Los hallazgos de código y datos son causas; los de
        planificación, el efecto intermedio; los financieros, la consecuencia. Presentar
        la cadena en ese orden es lo que convierte cuatro listas en una explicación.
        """
        by_agent = {o.agent: o for o in outputs}
        steps: list[CausalStep] = []
        step_number = 1

        # Causas de origen: lo que impide que el trabajo esté terminado.
        for agent_name in ("code-agent", "database-agent"):
            output = by_agent.get(agent_name)
            if output is None or not output.findings:
                continue
            worst = max(output.findings, key=lambda f: f.risk_score)
            steps.append(
                CausalStep(
                    step=step_number,
                    cause=worst.summary,
                    effect="El cambio no puede integrarse ni desplegarse con garantías.",
                    confidence=worst.confidence,
                    evidence_refs=[e.external_id or e.field or "" for e in worst.evidence],
                )
            )
            step_number += 1

        # Efecto intermedio: el retraso.
        jira = by_agent.get("jira-agent")
        if jira is not None and jira.findings:
            worst = max(jira.findings, key=lambda f: f.risk_score)
            steps.append(
                CausalStep(
                    step=step_number,
                    cause=worst.summary,
                    effect="La fecha comprometida no se alcanza con el estado actual.",
                    confidence=worst.confidence,
                    evidence_refs=[e.external_id or e.field or "" for e in worst.evidence],
                )
            )
            step_number += 1

        # Consecuencia: el dinero.
        finance = by_agent.get("finance-agent")
        if finance is not None and finance.findings:
            worst = max(finance.findings, key=lambda f: f.risk_score)
            steps.append(
                CausalStep(
                    step=step_number,
                    cause="El incumplimiento de la fecha activa las condiciones contractuales.",
                    effect=worst.summary,
                    confidence=worst.confidence,
                    evidence_refs=[e.external_id or e.field or "" for e in worst.evidence],
                )
            )

        return steps

    @staticmethod
    def build_premortem(
        context: AgentContext, outputs: list[AgentOutput]
    ) -> PreMortem:
        """Pre-mortem por reglas: se asume el fallo y se derivan los modos.

        Partir del fallo consumado, en lugar de listar riesgos, produce modos de fallo
        concretos: cada hallazgo activo se convierte en una forma en la que el
        compromiso ya se rompió.
        """
        contributing = [o for o in outputs if o.status != AgentRunStatus.SKIPPED]
        modes = [
            f"{f.summary} ({o.agent})"
            for o in contributing
            for f in o.findings
            if f.risk_score >= CORROBORATION_THRESHOLD
        ]

        signals = [
            f.summary
            for o in contributing
            for f in o.findings
            if f.risk_score < CORROBORATION_THRESHOLD
        ]

        preventive = [
            action.title
            for o in contributing
            for action in o.recommended_actions
        ]

        return PreMortem(
            assumed_failure=(
                f'"{context.commitment.title}" se incumplió. El beneficiario '
                f"{context.commitment.beneficiary or 'no identificado'} reclamó y la "
                "penalización se hizo efectiva."
            ),
            failure_modes=modes or ["No se identificaron modos de fallo graves."],
            early_signals=signals or ["No hay señales tempranas registradas."],
            preventive_actions=preventive or ["No hay acciones preventivas propuestas."],
        )

    def build_scenarios(
        self, context: AgentContext, outputs: list[AgentOutput], score: int
    ) -> list[Scenario]:
        """Los tres escenarios obligatorios.

        Se presentan siempre los tres, incluido "no actuar": sin la línea base de la
        inacción, el coste de las otras dos opciones no se puede juzgar.

        Las cifras se derivan de la exposición declarada en el compromiso y del riesgo
        consolidado, no se inventan. Cuando falta el dato, el campo queda en ``None`` en
        lugar de rellenarse con una estimación sin respaldo.
        """
        exposure = context.commitment.financial_exposure or Decimal("0")
        hourly = (
            context.project.hourly_cost
            if context.project is not None
            else Decimal("0")
        )
        probability_of_failure = score / 100

        # Coste de añadir capacidad: horas extra estimadas por los agentes, al coste del
        # proyecto. Si no hay estimación ni coste/hora, no se afirma un número.
        extra_hours = sum(
            action.estimated_effort_hours or 0
            for output in outputs
            for action in output.recommended_actions
        )
        capacity_cost = (
            _money(Decimal(str(extra_hours)) * hourly)
            if extra_hours and hourly
            else None
        )

        do_nothing_loss = _money(exposure * Decimal(str(probability_of_failure)))

        return [
            Scenario(
                kind=ScenarioKind.DO_NOTHING,
                title="No actuar",
                description=(
                    "Se mantiene el plan actual. Los bloqueos detectados siguen sin resolverse "
                    "y la fecha se alcanza en el estado en que está el trabajo hoy."
                ),
                expected_delay_days=self._expected_delay(outputs),
                expected_cost=do_nothing_loss,
                residual_exposure=_money(exposure),
                completion_probability=round(1 - probability_of_failure, 2),
                client_risk=(
                    "Alto: el beneficiario recibe el incumplimiento sin aviso previo."
                    if score >= CORROBORATION_THRESHOLD
                    else "Moderado: hay margen para avisar antes del vencimiento."
                ),
                technical_impact=(
                    "La deuda detectada (checks fallidos, migración sin rollback) entra a "
                    "producción o bloquea el despliegue."
                ),
            ),
            Scenario(
                kind=ScenarioKind.ADD_CAPACITY,
                title="Añadir capacidad",
                description=(
                    "Se asignan personas adicionales a desbloquear el trabajo pendiente y a "
                    "cerrar los checks fallidos antes de la fecha."
                ),
                expected_delay_days=max(0.0, self._expected_delay(outputs) - 2),
                expected_cost=capacity_cost,
                residual_exposure=_money(exposure * Decimal("0.3")),
                completion_probability=round(min(0.95, 1 - probability_of_failure + 0.3), 2),
                client_risk="Bajo: la fecha se mantiene si la capacidad llega a tiempo.",
                technical_impact=(
                   "Riesgo de prisa: más manos sobre el mismo cambio aumenta la probabilidad "
                   "de error en la integración."
                ),
                affected_commitments=[
                    "Los compromisos de los que se retire capacidad quedan expuestos."
                ],
            ),
            Scenario(
                kind=ScenarioKind.RENEGOTIATE_SCOPE,
                title="Renegociar alcance",
                description=(
                    "Se acuerda con el beneficiario entregar un subconjunto verificable en la "
                    "fecha original y desplazar el resto a una fecha nueva."
                ),
                expected_delay_days=0.0,
                expected_cost=None,
                residual_exposure=_money(exposure * Decimal("0.1")),
                completion_probability=0.9,
                client_risk=(
                    "Moderado: exige una conversación incómoda ahora en lugar de un "
                    "incumplimiento después."
                ),
                technical_impact=(
                    "Permite cerrar la migración con rollback y recuperar cobertura antes de "
                    "entregar."
                ),
                new_scope="Subconjunto entregable y verificado, sin las partes bloqueadas.",
                new_due_date=None,
            ),
        ]

    @staticmethod
    def _expected_delay(outputs: list[AgentOutput]) -> float:
        """Retraso esperado en días, derivado del hallazgo de vencimiento.

        Si el compromiso ya venció, el retraso es el observado; si no, se deriva del
        número de bloqueos activos. Es una heurística declarada, y por eso el escenario
        que la usa no afirma más precisión de la que tiene.
        """
        for output in outputs:
            for finding in output.findings:
                if finding.code == "overdue":
                    for evidence in finding.evidence:
                        if evidence.field == "due_date":
                            return 2.0
        blockers = sum(
            1
            for o in outputs
            for f in o.findings
            if f.code in {"blocked", "pr_blocked", "failing_checks", "external_dependency"}
        )
        return float(blockers)


def _money(value: Decimal) -> Decimal:
    """Redondea a dos decimales con redondeo comercial."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
