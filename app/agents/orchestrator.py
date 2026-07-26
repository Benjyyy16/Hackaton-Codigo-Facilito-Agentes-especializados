"""Orquestador de agentes.

Ejecuta los agentes especializados y compone su resultado en un único análisis. Sigue siendo
puro: sin E/S, sin red, sin base de datos. La coordinación de providers y la persistencia son
de ``OrchestratorService``, que es otra cosa.

Esa separación es deliberada. Un único "orquestador" que además hablara con providers y con la
base de datos perdería la propiedad que hace valiosa a esta capa: poder probar toda la lógica de
riesgo sin levantar nada.
"""

from __future__ import annotations

from typing import ClassVar

from app.agents.base import Agent, AgentContext, BaseAgent
from app.agents.commitment_agent import CommitmentAgent
from app.agents.financial_agent import FinancialAgent
from app.agents.risk_agent import RiskAgent
from app.agents.technical_agent import TechnicalAgent
from app.core.logging import get_logger
from app.schemas.analysis import AgentOutcome, AnalysisResult

logger = get_logger("agents.orchestrator")


class OrchestratorAgent(BaseAgent):
    """Compone el análisis a partir de los agentes especializados."""

    name: ClassVar[str] = "orchestrator"

    def __init__(
        self,
        agents: list[Agent] | None = None,
        risk_agent: RiskAgent | None = None,
    ) -> None:
        """Recibe los agentes por parámetro.

        Es inyección de dependencias, no adorno: permite ejecutar el orquestador con un
        subconjunto en un test, o sustituir un agente determinístico por uno respaldado por un
        LLM, sin tocar esta clase.
        """
        self._agents: list[Agent] = agents or [
            CommitmentAgent(),
            TechnicalAgent(),
            FinancialAgent(),
        ]
        self._risk = risk_agent or RiskAgent()

    def analyse(self, context: AgentContext) -> AnalysisResult:
        """Ejecuta los agentes y compone el análisis.

        Cada agente va en su propio ``try``: uno que revienta se registra, su contribución se
        omite y el análisis se marca como parcial en lugar de tumbar el flujo completo (RF-8.6).
        Perder una dimensión es peor que perder el análisis entero solo si nadie se entera, y de
        eso se encarga ``is_partial``.
        """
        outcomes: list[AgentOutcome] = []
        is_partial = False

        for agent in self._agents:
            try:
                outcomes.append(agent.run(context))
            except Exception as error:  # noqa: BLE001 - un agente caído no tumba el análisis
                is_partial = True
                logger.error(
                    "El agente %s falló durante el análisis",
                    getattr(agent, "name", type(agent).__name__),
                    exc_info=error,
                )

        risk_score, severity = self._risk.score(outcomes)
        dominant = self._risk.dominant_signal(outcomes)

        return AnalysisResult(
            risk_score=risk_score,
            severity=severity,
            is_partial=is_partial,
            financial_impact=self._financial_impact(outcomes),
            outcomes=outcomes,
            primary_reason=dominant.code if dominant else None,
        )

    def run(self, context: AgentContext) -> AgentOutcome:
        """Cumple el protocolo ``Agent`` devolviendo el resultado compuesto."""
        result = self.analyse(context)
        return AgentOutcome(
            agent=self.name,
            score=result.risk_score,
            signals=result.signals,
            detail={
                "severity": result.severity.value,
                "is_partial": result.is_partial,
                "financial_impact": result.financial_impact,
            },
        )

    @staticmethod
    def _financial_impact(outcomes: list[AgentOutcome]) -> float:
        """Toma el impacto económico del agente financiero.

        No se recalcula aquí: la fórmula vive en un solo sitio, y duplicarla garantizaría que las
        dos copias divergieran.
        """
        for outcome in outcomes:
            if outcome.agent == FinancialAgent.name:
                value = outcome.detail.get("financial_impact")
                if isinstance(value, (int, float)):
                    return max(0.0, float(value))
        return 0.0
