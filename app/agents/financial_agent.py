"""Agente financiero.

Traduce el retraso a dinero, que es lo que convierte una alerta técnica en una decisión de
negocio. Es el único sitio donde vive la fórmula del impacto económico.
"""

from __future__ import annotations

from typing import ClassVar, Final

from app.agents.base import AgentContext, BaseAgent
from app.schemas.analysis import AgentOutcome, Signal

#: Horas que se asumen cuando no hay estimación. Es un supuesto, no un dato, y por eso el
#: resultado lo declara en ``detail`` para que quien lo lea sepa que es estimado.
DEFAULT_ESTIMATED_HOURS: Final[float] = 8.0

#: Tramos de impacto, en unidades monetarias, y su peso.
IMPACT_LOW: Final[float] = 500.0
IMPACT_MEDIUM: Final[float] = 2_000.0
IMPACT_HIGH: Final[float] = 10_000.0

WEIGHT_IMPACT_LOW: Final[int] = 25
WEIGHT_IMPACT_MEDIUM: Final[int] = 50
WEIGHT_IMPACT_HIGH: Final[int] = 75
WEIGHT_IMPACT_CRITICAL: Final[int] = 95
WEIGHT_UNKNOWN_COST: Final[int] = 15


class FinancialAgent(BaseAgent):
    """Estima el impacto económico del riesgo."""

    name: ClassVar[str] = "financial"

    def run(self, context: AgentContext) -> AgentOutcome:
        project = context.project
        hourly_cost = project.hourly_cost if project else 0.0

        hours, hours_estimated = self._hours_at_risk(context)
        overdue_days = self._overdue_days(context)

        # El retraso multiplica: cada día vencido arrastra el trabajo pendiente otra vez.
        delay_multiplier = 1.0 + min(overdue_days, 30) / 10
        impact = round(hours * hourly_cost * delay_multiplier, 2)

        signals: list[Signal] = []

        if hourly_cost <= 0:
            # Sin coste por hora el impacto sale cero y las alertas pierden su mejor argumento.
            # Se avisa como hallazgo propio en lugar de dejar un cero silencioso.
            signals.append(
                Signal(
                    code="missing_hourly_cost",
                    message=(
                        "El contenedor no tiene coste por hora configurado; "
                        "el impacto económico no se puede calcular."
                    ),
                    weight=WEIGHT_UNKNOWN_COST,
                )
            )
        else:
            signals.append(self._impact_signal(impact))

        return self._outcome(
            signals,
            detail={
                "financial_impact": impact,
                "hours_at_risk": hours,
                "hours_were_estimated": hours_estimated,
                "hourly_cost": hourly_cost,
                "overdue_days": overdue_days,
                "delay_multiplier": round(delay_multiplier, 2),
            },
        )

    @staticmethod
    def _hours_at_risk(context: AgentContext) -> tuple[float, bool]:
        """Horas comprometidas, y si hubo que suponerlas."""
        commitment = context.commitment
        if commitment is not None and commitment.estimated_hours:
            return float(commitment.estimated_hours), False
        if context.event.estimated_hours:
            return float(context.event.estimated_hours), False
        return DEFAULT_ESTIMATED_HOURS, True

    @staticmethod
    def _overdue_days(context: AgentContext) -> int:
        """Días de retraso. Cero si aún no ha vencido o no hay fecha."""
        commitment = context.commitment
        due_date = commitment.due_date if commitment else context.event.due_date
        if due_date is None:
            return 0
        elapsed = (context.now - due_date).total_seconds()
        return max(0, int(elapsed // 86400))

    @staticmethod
    def _impact_signal(impact: float) -> Signal:
        """Traduce el importe a un hallazgo con su peso."""
        if impact >= IMPACT_HIGH:
            weight, label = WEIGHT_IMPACT_CRITICAL, "crítico"
        elif impact >= IMPACT_MEDIUM:
            weight, label = WEIGHT_IMPACT_HIGH, "alto"
        elif impact >= IMPACT_LOW:
            weight, label = WEIGHT_IMPACT_MEDIUM, "moderado"
        else:
            weight, label = WEIGHT_IMPACT_LOW, "bajo"

        return Signal(
            code="financial_exposure",
            message=f"Exposición económica {label}: {impact:.2f}.",
            weight=weight,
        )
