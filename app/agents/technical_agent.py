"""Agente técnico.

Mira cómo se está ejecutando el trabajo: bloqueos, ausencia de responsable, estancamiento y
vaivén de reasignaciones. Responde a "¿hay algo atascando esto?".

Trabaja sobre ``ExternalEvent``, así que las mismas reglas se aplican a un issue de Jira, a un
pull request de GitHub o a una página de Notion. Ahí está el valor de que el evento sea agnóstico.
"""

from __future__ import annotations

from typing import ClassVar, Final

from app.agents.base import AgentContext, BaseAgent
from app.schemas.analysis import AgentOutcome, Signal
from app.schemas.events import EventKind

#: Etiquetas y estados que indican bloqueo, en los idiomas que se ven en la práctica.
BLOCKED_MARKERS: Final[frozenset[str]] = frozenset(
    {"blocked", "bloqueado", "impediment", "impedimento", "on hold", "en espera"}
)

#: Días sin actividad a partir de los cuales el trabajo se considera estancado.
STALE_DAYS: Final[int] = 7

#: Reasignaciones en el historial reciente que delatan falta de dueño claro.
REASSIGNMENT_LIMIT: Final[int] = 2

WEIGHT_BLOCKED: Final[int] = 80
WEIGHT_UNASSIGNED: Final[int] = 45
WEIGHT_STALE: Final[int] = 55
WEIGHT_CHURN: Final[int] = 50
WEIGHT_NEGATIVE_REVIEW: Final[int] = 60


class TechnicalAgent(BaseAgent):
    """Evalúa señales de ejecución del trabajo."""

    name: ClassVar[str] = "technical"

    def run(self, context: AgentContext) -> AgentOutcome:
        event = context.event
        signals: list[Signal] = []

        if self._is_blocked(context):
            signals.append(
                Signal(
                    code="blocked",
                    message="El trabajo está marcado como bloqueado.",
                    weight=WEIGHT_BLOCKED,
                )
            )

        if not event.owner:
            signals.append(
                Signal(
                    code="unassigned",
                    message="El trabajo no tiene responsable asignado.",
                    weight=WEIGHT_UNASSIGNED,
                )
            )

        stale_days = self._days_since_activity(context)
        if stale_days is not None and stale_days >= STALE_DAYS:
            signals.append(
                Signal(
                    code="stale",
                    message=f"Sin actividad desde hace {stale_days} días.",
                    weight=WEIGHT_STALE,
                )
            )

        reassignments = self._count_reassignments(context)
        if reassignments >= REASSIGNMENT_LIMIT:
            signals.append(
                Signal(
                    code="ownership_churn",
                    message=f"El responsable cambió {reassignments} veces.",
                    weight=WEIGHT_CHURN,
                )
            )

        if event.kind is EventKind.REVIEW_REQUESTED and not event.owner:
            signals.append(
                Signal(
                    code="review_without_reviewer",
                    message="Se pidió revisión sin nadie que la haga.",
                    weight=WEIGHT_NEGATIVE_REVIEW,
                )
            )

        return self._outcome(
            signals,
            detail={
                "stale_days": stale_days,
                "reassignments": reassignments,
                "state": event.state,
            },
        )

    @staticmethod
    def _is_blocked(context: AgentContext) -> bool:
        """Busca marcas de bloqueo en estado, etiquetas y comentario."""
        event = context.event
        haystack = [event.state or "", *event.labels]
        if event.comment:
            haystack.append(event.comment)
        lowered = " ".join(haystack).lower()
        return any(marker in lowered for marker in BLOCKED_MARKERS)

    @staticmethod
    def _days_since_activity(context: AgentContext) -> int | None:
        """Días desde el evento más reciente conocido.

        Se calcula contra el evento actual, no contra el histórico, porque el evento actual es
        por definición la última actividad observada. Devuelve ``None`` si el instante está en
        el futuro, que solo puede ser un desajuste de reloj.
        """
        elapsed = (context.now - context.event.occurred_at).total_seconds()
        if elapsed < 0:
            return None
        return int(elapsed // 86400)

    @staticmethod
    def _count_reassignments(context: AgentContext) -> int:
        """Cuenta cambios de responsable en el evento y en el historial reciente."""
        owner_fields = {"assignee", "owner", "responsable", "asignado"}
        events = [context.event, *context.recent_events]
        return sum(
            1
            for item in events
            for change in item.changes
            if change.field.lower() in owner_fields
        )
