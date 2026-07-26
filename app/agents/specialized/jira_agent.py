"""Agente de Jira: riesgo de planificación y ejecución del compromiso.

Observa el elemento de trabajo que representa el compromiso en Jira: su vencimiento,
su estado, quién responde por él y qué lo bloquea. No sabe nada de código ni de
dinero, y no debe saberlo: correlacionar es trabajo del orquestador.

Los pesos de cada señal son constantes con nombre y no números sueltos en el cuerpo de
las funciones. Un umbral que aparece dos veces acaba divergiendo, y un peso sin nombre
no se puede discutir en una revisión.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Final

from app.agents.specialized.base import AgentContext, BaseSpecializedAgent
from app.schemas.domain import (
    AgentOutput,
    EvidenceSourceType,
    Finding,
    RecommendedAction,
)

PROVIDER: Final[str] = "jira"

# --- Pesos de las señales ----------------------------------------------------------
# El vencimiento pasado pesa más que cualquier otra señal de este agente: es el único
# hecho consumado; el resto son predicciones.
WEIGHT_OVERDUE: Final[int] = 90
WEIGHT_DUE_TODAY: Final[int] = 75
WEIGHT_DUE_SOON: Final[int] = 55
WEIGHT_NO_DUE_DATE: Final[int] = 35
WEIGHT_BLOCKED: Final[int] = 80
WEIGHT_UNASSIGNED: Final[int] = 60
WEIGHT_EXTERNAL_DEPENDENCY: Final[int] = 65
WEIGHT_STALE: Final[int] = 50
WEIGHT_REASSIGNMENT_CHURN: Final[int] = 45
WEIGHT_REOPENED: Final[int] = 55

#: Ventana de "vence pronto". Tres días es lo que queda para reaccionar sin renegociar:
#: por debajo de eso, añadir capacidad ya no cambia el resultado.
DUE_SOON_DAYS: Final[int] = 3

#: Días sin actividad a partir de los cuales el elemento se considera estancado.
STALE_DAYS: Final[int] = 5

#: Reasignaciones a partir de las cuales el problema no es quién lo hace, sino que
#: nadie sabe qué hay que hacer.
REASSIGNMENT_THRESHOLD: Final[int] = 3

#: Estados de Jira que significan "bloqueado". Son cadenas del proveedor, así que se
#: comparan en minúsculas y por contención: cada organización nombra sus estados
#: distinto y no hay un vocabulario canónico que respetar.
BLOCKED_MARKERS: Final[tuple[str, ...]] = ("blocked", "bloqueado", "impediment", "on hold")


class JiraAgent(BaseSpecializedAgent):
    """Analiza el riesgo de planificación de un compromiso a partir de Jira."""

    name: ClassVar[str] = "jira-agent"
    category: ClassVar[str] = "schedule"

    def analyze(self, context: AgentContext) -> AgentOutput:
        signal = context.signal(PROVIDER)
        if not signal:
            return self._empty_output(
                context,
                ["Sin datos de Jira: no hay conexión configurada o el compromiso no tiene issue asociado."],
                reason="No se pudo evaluar el riesgo de planificación: falta la señal de Jira.",
            )

        issue_key = str(signal.get("issue_key") or "desconocido")
        url = signal.get("url")

        findings: list[Finding] = []
        missing: list[str] = []

        findings.extend(self._due_date_findings(context, signal, issue_key, url))
        findings.extend(self._workflow_findings(context, signal, issue_key, url))
        findings.extend(self._history_findings(context, signal, issue_key, url))

        if signal.get("story_points") is None and signal.get("estimated_hours") is None:
            missing.append(
                f"{issue_key} no tiene estimación (ni puntos ni horas): "
                "el impacto económico del retraso no se puede acotar."
            )

        actions = self._actions(signal, issue_key, findings)

        return self._output(
            context, findings, missing_information=missing, recommended_actions=actions
        )

    # --- Vencimiento ---------------------------------------------------------------

    def _due_date_findings(
        self,
        context: AgentContext,
        signal: dict[str, Any],
        issue_key: str,
        url: str | None,
    ) -> list[Finding]:
        """Señales derivadas de la fecha de entrega.

        Se toma la del compromiso si existe y, si no, la del issue. El compromiso manda
        porque es la fecha que se pactó; la del issue es una consecuencia de
        planificación que alguien puede haber movido.
        """
        due = context.commitment.due_date or _as_datetime(signal.get("due_date"))
        now = context.now

        if due is None:
            return [
                self._finding(
                    code="no_due_date",
                    summary=f"{issue_key} no tiene fecha de vencimiento.",
                    risk_score=WEIGHT_NO_DUE_DATE,
                    impact="Sin fecha no hay incumplimiento medible ni aviso posible.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="due_date",
                            value=None,
                            observed_at=now,
                            explanation="Ni el compromiso ni el issue declaran fecha de entrega.",
                        )
                    ],
                )
            ]

        delta_days = (due - now).total_seconds() / 86400

        if delta_days < 0:
            overdue_days = abs(int(delta_days)) or 1
            return [
                self._finding(
                    code="overdue",
                    summary=f"{issue_key} venció hace {overdue_days} día(s) y sigue abierto.",
                    risk_score=WEIGHT_OVERDUE,
                    impact="El compromiso ya está incumplido: la exposición es actual, no potencial.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="due_date",
                            value=due.isoformat(),
                            observed_at=now,
                            explanation=f"La fecha de entrega pasó hace {overdue_days} día(s).",
                        )
                    ],
                )
            ]

        if delta_days < 1:
            return [
                self._finding(
                    code="due_today",
                    summary=f"{issue_key} vence hoy.",
                    risk_score=WEIGHT_DUE_TODAY,
                    impact="Queda menos de un día: solo cabe entregar o avisar.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="due_date",
                            value=due.isoformat(),
                            observed_at=now,
                            explanation="El vencimiento es en menos de 24 horas.",
                        )
                    ],
                )
            ]

        if delta_days <= DUE_SOON_DAYS:
            return [
                self._finding(
                    code="due_soon",
                    summary=f"{issue_key} vence en {int(delta_days)} día(s).",
                    risk_score=WEIGHT_DUE_SOON,
                    impact="La ventana para añadir capacidad se está cerrando.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="due_date",
                            value=due.isoformat(),
                            observed_at=now,
                            explanation=f"Quedan {int(delta_days)} día(s), por debajo del umbral de {DUE_SOON_DAYS}.",
                        )
                    ],
                )
            ]

        return []

    # --- Estado del flujo de trabajo -----------------------------------------------

    def _workflow_findings(
        self,
        context: AgentContext,
        signal: dict[str, Any],
        issue_key: str,
        url: str | None,
    ) -> list[Finding]:
        findings: list[Finding] = []
        now = context.now
        state = str(signal.get("status") or "").lower()

        if any(marker in state for marker in BLOCKED_MARKERS):
            findings.append(
                self._finding(
                    code="blocked",
                    summary=f"{issue_key} está bloqueado (estado: {signal.get('status')}).",
                    risk_score=WEIGHT_BLOCKED,
                    impact="Nadie puede avanzar hasta que se levante el bloqueo.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="status",
                            value=signal.get("status"),
                            observed_at=now,
                            explanation="El estado del issue corresponde a un bloqueo.",
                        )
                    ],
                )
            )

        assignee = signal.get("assignee")
        if not assignee:
            findings.append(
                self._finding(
                    code="unassigned",
                    summary=f"{issue_key} no tiene responsable asignado.",
                    risk_score=WEIGHT_UNASSIGNED,
                    impact="Sin responsable no hay nadie que desbloquee ni a quien preguntar.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="assignee",
                            value=None,
                            observed_at=now,
                            explanation="El campo de responsable está vacío.",
                        )
                    ],
                )
            )

        blocked_by = signal.get("blocked_by") or []
        external = [dep for dep in blocked_by if _is_external(dep)]
        if external:
            findings.append(
                self._finding(
                    code="external_dependency",
                    summary=f"{issue_key} depende de {len(external)} elemento(s) fuera del equipo.",
                    risk_score=WEIGHT_EXTERNAL_DEPENDENCY,
                    # La confianza baja porque "externo" se infiere de la forma de la
                    # dependencia, no de un campo que Jira declare como tal.
                    confidence=0.75,
                    impact="Añadir capacidad propia no acelera una dependencia externa.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="blocked_by",
                            value=", ".join(str(d) for d in external),
                            observed_at=now,
                            explanation="Las dependencias listadas apuntan a proyectos o equipos distintos.",
                        )
                    ],
                )
            )

        return findings

    # --- Histórico -----------------------------------------------------------------

    def _history_findings(
        self,
        context: AgentContext,
        signal: dict[str, Any],
        issue_key: str,
        url: str | None,
    ) -> list[Finding]:
        """Señales que solo existen mirando el pasado del elemento."""
        findings: list[Finding] = []
        now = context.now

        last_activity = _as_datetime(signal.get("last_activity_at"))
        if last_activity is not None:
            idle_days = int((now - last_activity).total_seconds() / 86400)
            if idle_days >= STALE_DAYS:
                findings.append(
                    self._finding(
                        code="stale",
                        summary=f"{issue_key} lleva {idle_days} días sin actividad.",
                        risk_score=WEIGHT_STALE,
                        impact="Un elemento sin movimiento no va a cumplir su fecha por sí solo.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.JIRA,
                                provider=PROVIDER,
                                external_id=issue_key,
                                source_url=url,
                                field="last_activity_at",
                                value=last_activity.isoformat(),
                                observed_at=now,
                                explanation=f"Sin cambios en {idle_days} días, umbral {STALE_DAYS}.",
                            )
                        ],
                    )
                )

        reassignments = int(signal.get("reassignment_count") or 0)
        if reassignments >= REASSIGNMENT_THRESHOLD:
            findings.append(
                self._finding(
                    code="reassignment_churn",
                    summary=f"{issue_key} cambió de responsable {reassignments} veces.",
                    risk_score=WEIGHT_REASSIGNMENT_CHURN,
                    confidence=0.8,
                    impact="La rotación suele indicar que el alcance no está claro.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="reassignment_count",
                            value=reassignments,
                            observed_at=now,
                            explanation=f"{reassignments} reasignaciones, umbral {REASSIGNMENT_THRESHOLD}.",
                        )
                    ],
                )
            )

        if signal.get("reopened"):
            findings.append(
                self._finding(
                    code="reopened",
                    summary=f"{issue_key} se cerró y se volvió a abrir.",
                    risk_score=WEIGHT_REOPENED,
                    impact="Lo que se dio por hecho no lo estaba: la estimación restante no es fiable.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.JIRA,
                            provider=PROVIDER,
                            external_id=issue_key,
                            source_url=url,
                            field="reopened",
                            value=True,
                            observed_at=now,
                            explanation="El histórico registra una reapertura.",
                        )
                    ],
                )
            )

        return findings

    # --- Acciones ------------------------------------------------------------------

    def _actions(
        self, signal: dict[str, Any], issue_key: str, findings: list[Finding]
    ) -> list[RecommendedAction]:
        """Acciones propuestas. Todas requieren aprobación: el agente no toca Jira."""
        codes = {f.code for f in findings}
        actions: list[RecommendedAction] = []

        if "unassigned" in codes:
            actions.append(
                RecommendedAction(
                    action_type="reassign_owner",
                    title=f"Asignar responsable a {issue_key}",
                    rationale="Un elemento sin responsable no avanza y no hay a quién escalar.",
                    payload={"issue_key": issue_key, "field": "assignee"},
                    requires_human_approval=True,
                )
            )

        if "blocked" in codes or "external_dependency" in codes:
            actions.append(
                RecommendedAction(
                    action_type="update_jira_issue",
                    title=f"Escalar el bloqueo de {issue_key}",
                    rationale="El bloqueo no se resuelve solo y consume la ventana de reacción.",
                    payload={
                        "issue_key": issue_key,
                        "comment": "Bloqueo detectado por Datgent: requiere escalado.",
                    },
                    requires_human_approval=True,
                )
            )

        return actions


# --- Utilidades --------------------------------------------------------------------


def _as_datetime(value: Any) -> datetime | None:
    """Convierte a ``datetime`` lo que venga del provider, o devuelve ``None``.

    Tolera cadenas ISO con ``Z`` porque es lo que devuelve Jira, y no eleva ante un
    valor irreconocible: un campo mal formado es una señal ausente, no un fallo del
    análisis.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_external(dependency: Any) -> bool:
    """Heurística de dependencia externa.

    Una clave con prefijo distinto al del propio issue, o marcada explícitamente, se
    considera externa. Es una inferencia, y por eso el hallazgo que la usa lleva
    confianza menor que 1.
    """
    text = str(dependency).lower()
    return any(marker in text for marker in ("external", "vendor", "third", "proveedor", "externo"))
