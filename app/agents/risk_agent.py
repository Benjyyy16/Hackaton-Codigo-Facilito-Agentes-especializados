"""Agente de riesgo.

No mira el evento: mira lo que dijeron los demás agentes y compone la puntuación global. Es el
único que decide cuánto pesa cada dimensión.
"""

from __future__ import annotations

from typing import ClassVar, Final

from app.agents.base import AgentContext, BaseAgent
from app.schemas.analysis import AgentOutcome, Severity, Signal, severity_for_score

#: Pesos de cada dimensión. Constantes con nombre y no números sueltos, para que el umbral de
#: alerta sea razonable y auditable: quien discuta una alerta puede discutir estos tres valores.
#:
#: Suman 1.0 a propósito, de forma que la puntuación global se mantenga en la escala 0–100 sin
#: normalizaciones sorpresa.
WEIGHT_COMMITMENT: Final[float] = 0.45
WEIGHT_TECHNICAL: Final[float] = 0.30
WEIGHT_FINANCIAL: Final[float] = 0.25

#: Suelo que impone una señal grave. Sin él, un hallazgo crítico en una sola dimensión quedaría
#: diluido por las otras dos y no llegaría a abrir alerta, que es justo lo que no se quiere.
CRITICAL_SIGNAL_FLOOR: Final[int] = 70
CRITICAL_SIGNAL_THRESHOLD: Final[int] = 90

DIMENSION_WEIGHTS: Final[dict[str, float]] = {
    "commitment": WEIGHT_COMMITMENT,
    "technical": WEIGHT_TECHNICAL,
    "financial": WEIGHT_FINANCIAL,
}


class RiskAgent(BaseAgent):
    """Compone la puntuación global a partir de los resultados de los demás agentes."""

    name: ClassVar[str] = "risk"

    def score(self, outcomes: list[AgentOutcome]) -> tuple[int, Severity]:
        """Combina los resultados en una puntuación 0–100 y su severidad (RF-8.5).

        Los pesos se renormalizan sobre las dimensiones **presentes**. Si un agente falló y su
        resultado no llegó, lo correcto es repartir su peso entre los demás; mantenerlo haría
        que un análisis parcial pareciera menos grave solo por faltar información.
        """
        present = {
            outcome.agent: outcome
            for outcome in outcomes
            if outcome.agent in DIMENSION_WEIGHTS
        }
        if not present:
            return 0, Severity.LOW

        total_weight = sum(DIMENSION_WEIGHTS[name] for name in present)
        weighted = sum(
            outcome.score * DIMENSION_WEIGHTS[name] for name, outcome in present.items()
        )
        score = int(round(weighted / total_weight))

        # Un hallazgo grave impone un suelo, no importa cómo salga la media.
        if any(
            signal.weight >= CRITICAL_SIGNAL_THRESHOLD
            for outcome in outcomes
            for signal in outcome.signals
        ):
            score = max(score, CRITICAL_SIGNAL_FLOOR)

        score = max(0, min(score, 100))
        return score, severity_for_score(score)

    def run(self, context: AgentContext) -> AgentOutcome:
        """Presente para cumplir el protocolo.

        La composición real necesita los resultados de los demás agentes, que el contexto no
        lleva, así que el orquestador invoca ``score()``. Se deja explícito en lugar de fingir un
        cálculo con datos que no tiene.
        """
        return self._outcome(
            [],
            detail={
                "note": (
                    "RiskAgent compone resultados de otros agentes; "
                    "el orquestador invoca score()."
                ),
                "weights": DIMENSION_WEIGHTS,
            },
        )

    @staticmethod
    def dominant_signal(outcomes: list[AgentOutcome]) -> Signal | None:
        """Hallazgo de mayor peso, que da motivo a la alerta.

        Ese motivo forma parte de la identidad de la alerta abierta, así que ante empate se
        desempata por el código alfabéticamente: sin un criterio estable, dos análisis idénticos
        podrían elegir motivos distintos y abrir dos alertas para lo mismo.
        """
        signals = [signal for outcome in outcomes for signal in outcome.signals]
        if not signals:
            return None
        return max(signals, key=lambda signal: (signal.weight, signal.code))
