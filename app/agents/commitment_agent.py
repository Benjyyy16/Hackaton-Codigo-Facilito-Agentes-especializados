"""Agente de compromisos.

Mira el compromiso en sí: cuándo vence, en qué estado está y si se ha reabierto. Es el agente
que responde a "¿vamos a llegar?".
"""

from __future__ import annotations

from typing import ClassVar, Final

from app.agents.base import AgentContext, BaseAgent
from app.schemas.analysis import AgentOutcome, CommitmentStatus, Signal

#: Umbral de proximidad del vencimiento, en días.
DUE_SOON_DAYS: Final[int] = 3
DUE_APPROACHING_DAYS: Final[int] = 7

# Pesos con nombre en lugar de números sueltos, para que el umbral de alerta sea auditable.
WEIGHT_OVERDUE: Final[int] = 90
WEIGHT_BREACHED: Final[int] = 95
WEIGHT_DUE_SOON: Final[int] = 65
WEIGHT_DUE_APPROACHING: Final[int] = 40
WEIGHT_NO_DUE_DATE: Final[int] = 30
WEIGHT_REOPENED: Final[int] = 55


class CommitmentAgent(BaseAgent):
    """Evalúa el estado del compromiso frente a su fecha."""

    name: ClassVar[str] = "commitment"

    def run(self, context: AgentContext) -> AgentOutcome:
        signals: list[Signal] = []
        commitment = context.commitment
        due_date = commitment.due_date if commitment else context.event.due_date

        if commitment is not None and commitment.status is CommitmentStatus.BREACHED:
            signals.append(
                Signal(
                    code="commitment_breached",
                    message="El compromiso ya está marcado como incumplido.",
                    weight=WEIGHT_BREACHED,
                )
            )

        if commitment is not None and commitment.status is CommitmentStatus.MET:
            # Un compromiso cumplido no aporta riesgo, y decirlo explícitamente evita que el
            # resto de señales lo arrastren.
            return self._outcome(
                [], detail={"status": commitment.status.value, "closed": True}
            )

        if due_date is None:
            # La ausencia de fecha es un riesgo en sí: sin ella no hay compromiso medible.
            signals.append(
                Signal(
                    code="missing_due_date",
                    message="El compromiso no tiene fecha de vencimiento.",
                    weight=WEIGHT_NO_DUE_DATE,
                )
            )
        else:
            remaining_days = (due_date - context.now).total_seconds() / 86400
            if remaining_days < 0:
                signals.append(
                    Signal(
                        code="overdue",
                        message=(
                            f"El vencimiento pasó hace {abs(int(remaining_days))} días."
                        ),
                        weight=WEIGHT_OVERDUE,
                    )
                )
            elif remaining_days <= DUE_SOON_DAYS:
                signals.append(
                    Signal(
                        code="due_soon",
                        message=f"Vence en {int(remaining_days)} días o menos.",
                        weight=WEIGHT_DUE_SOON,
                    )
                )
            elif remaining_days <= DUE_APPROACHING_DAYS:
                signals.append(
                    Signal(
                        code="due_approaching",
                        message=f"Vence en {int(remaining_days)} días.",
                        weight=WEIGHT_DUE_APPROACHING,
                    )
                )

        if self._was_reopened(context):
            signals.append(
                Signal(
                    code="reopened",
                    message="El elemento volvió a un estado anterior tras darse por hecho.",
                    weight=WEIGHT_REOPENED,
                )
            )

        return self._outcome(
            signals,
            detail={
                "due_date": due_date.isoformat() if due_date else None,
                "status": commitment.status.value if commitment else None,
            },
        )

    @staticmethod
    def _was_reopened(context: AgentContext) -> bool:
        """Detecta una reapertura en los cambios del evento.

        Se busca en los cambios declarados y no en el estado actual, porque un elemento reabierto
        y vuelto a cerrar deja rastro solo en el histórico.
        """
        closed_states = {"done", "closed", "resolved", "completado", "cerrado"}
        for change in context.event.changes:
            if change.field.lower() not in {"status", "estado", "state"}:
                continue
            came_from = (change.from_value or "").strip().lower()
            went_to = (change.to_value or "").strip().lower()
            if came_from in closed_states and went_to not in closed_states:
                return True
        return False
