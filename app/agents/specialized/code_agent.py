"""Agente de código: riesgo técnico del compromiso a partir de GitHub.

Observa lo que el repositorio dice sobre la entrega: si el cambio está listo para
integrarse, si los checks pasan, si hay pruebas y si la migración es reversible.

La distinción que importa es entre "el trabajo está hecho" y "el trabajo está
integrado". Un pull request abierto con checks en verde es trabajo hecho que todavía no
está entregado, y eso es riesgo aunque el tablero diga que la tarea está lista.
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

PROVIDER: Final[str] = "github"

# --- Pesos de las señales ----------------------------------------------------------
# Un check fallido es un hecho verificable; la falta de cobertura es una inferencia
# sobre el futuro. Por eso el primero pesa más.
WEIGHT_FAILING_CHECKS: Final[int] = 85
WEIGHT_PR_BLOCKED: Final[int] = 75
WEIGHT_PR_OPEN_NEAR_DUE: Final[int] = 60
WEIGHT_NO_TESTS: Final[int] = 65
WEIGHT_LOW_COVERAGE: Final[int] = 50
WEIGHT_RISKY_MIGRATION: Final[int] = 80
WEIGHT_LARGE_DIFF: Final[int] = 45
WEIGHT_NO_REVIEW: Final[int] = 55
WEIGHT_STALE_PR: Final[int] = 50

#: Cobertura por debajo de la cual el cambio se considera insuficientemente probado.
COVERAGE_FLOOR: Final[int] = 60

#: Líneas cambiadas a partir de las cuales una revisión deja de ser efectiva. No es un
#: número mágico: por encima de este tamaño el revisor aprueba por confianza, no por
#: lectura.
LARGE_DIFF_LINES: Final[int] = 400

#: Días que un PR puede estar abierto sin revisión antes de considerarse estancado.
STALE_PR_DAYS: Final[int] = 3

#: Patrones en ficheros de migración que indican una operación no reversible.
DESTRUCTIVE_SQL_MARKERS: Final[tuple[str, ...]] = (
    "drop table",
    "drop column",
    "truncate",
    "delete from",
    "alter column",
)


class CodeAgent(BaseSpecializedAgent):
    """Analiza el riesgo técnico de un compromiso a partir del repositorio."""

    name: ClassVar[str] = "code-agent"
    category: ClassVar[str] = "technical"

    def analyze(self, context: AgentContext) -> AgentOutput:
        signal = context.signal(PROVIDER)
        if not signal:
            return self._empty_output(
                context,
                ["Sin datos de GitHub: no hay repositorio conectado al compromiso."],
                reason="No se pudo evaluar el riesgo técnico: falta la señal de GitHub.",
            )

        findings: list[Finding] = []
        missing: list[str] = []

        findings.extend(self._pull_request_findings(context, signal))
        findings.extend(self._check_findings(context, signal))
        findings.extend(self._quality_findings(context, signal, missing))
        findings.extend(self._migration_findings(context, signal))

        actions = self._actions(signal, findings)

        return self._output(
            context, findings, missing_information=missing, recommended_actions=actions
        )

    # --- Pull requests -------------------------------------------------------------

    def _pull_request_findings(
        self, context: AgentContext, signal: dict[str, Any]
    ) -> list[Finding]:
        findings: list[Finding] = []
        now = context.now
        repo = str(signal.get("repository") or "desconocido")

        for pr in signal.get("pull_requests") or []:
            number = pr.get("number")
            ref = f"{repo}#{number}"
            url = pr.get("url")
            state = str(pr.get("state") or "").lower()

            if state != "open":
                continue

            if pr.get("mergeable") is False or pr.get("has_conflicts"):
                findings.append(
                    self._finding(
                        code="pr_blocked",
                        summary=f"{ref} no se puede integrar (conflictos o merge bloqueado).",
                        risk_score=WEIGHT_PR_BLOCKED,
                        impact="El trabajo existe pero no puede llegar a producción.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.GITHUB,
                                provider=PROVIDER,
                                external_id=ref,
                                source_url=url,
                                field="mergeable",
                                value=pr.get("mergeable"),
                                observed_at=now,
                                explanation="GitHub reporta el pull request como no integrable.",
                            )
                        ],
                    )
                )

            if not pr.get("approved_reviews"):
                findings.append(
                    self._finding(
                        code="no_review",
                        summary=f"{ref} sigue sin aprobación de revisión.",
                        risk_score=WEIGHT_NO_REVIEW,
                        impact="Sin revisión el cambio no puede integrarse ni se ha validado.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.GITHUB,
                                provider=PROVIDER,
                                external_id=ref,
                                source_url=url,
                                field="approved_reviews",
                                value=pr.get("approved_reviews", 0),
                                observed_at=now,
                                explanation="El pull request no acumula revisiones aprobadas.",
                            )
                        ],
                    )
                )

            opened = _as_datetime(pr.get("created_at"))
            if opened is not None:
                open_days = int((now - opened).total_seconds() / 86400)
                if open_days >= STALE_PR_DAYS:
                    findings.append(
                        self._finding(
                            code="stale_pr",
                            summary=f"{ref} lleva {open_days} días abierto.",
                            risk_score=WEIGHT_STALE_PR,
                            impact="Un pull request que envejece acumula conflictos y pierde contexto.",
                            evidence=[
                                self._evidence(
                                    source_type=EvidenceSourceType.GITHUB,
                                    provider=PROVIDER,
                                    external_id=ref,
                                    source_url=url,
                                    field="created_at",
                                    value=opened.isoformat(),
                                    observed_at=now,
                                    explanation=f"Abierto hace {open_days} días, umbral {STALE_PR_DAYS}.",
                                )
                            ],
                        )
                    )

            # Un PR abierto cerca del vencimiento es riesgo aunque todo lo demás esté
            # bien: falta el paso de integrar, y ese paso puede fallar.
            due = context.commitment.due_date
            if due is not None and (due - now).total_seconds() / 86400 <= 2:
                findings.append(
                    self._finding(
                        code="pr_open_near_due",
                        summary=f"{ref} sigue abierto a menos de 2 días del vencimiento.",
                        risk_score=WEIGHT_PR_OPEN_NEAR_DUE,
                        confidence=0.85,
                        impact="Integrar todavía puede fallar y ya no quedaría margen.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.GITHUB,
                                provider=PROVIDER,
                                external_id=ref,
                                source_url=url,
                                field="state",
                                value="open",
                                observed_at=now,
                                explanation="El cambio no está integrado y el vencimiento es inminente.",
                            )
                        ],
                    )
                )

            diff_size = int(pr.get("additions") or 0) + int(pr.get("deletions") or 0)
            if diff_size >= LARGE_DIFF_LINES:
                findings.append(
                    self._finding(
                        code="large_diff",
                        summary=f"{ref} cambia {diff_size} líneas.",
                        risk_score=WEIGHT_LARGE_DIFF,
                        confidence=0.7,
                        impact="Por encima de este tamaño la revisión deja de ser efectiva.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.GITHUB,
                                provider=PROVIDER,
                                external_id=ref,
                                source_url=url,
                                field="diff_size",
                                value=diff_size,
                                observed_at=now,
                                explanation=f"{diff_size} líneas, umbral {LARGE_DIFF_LINES}.",
                            )
                        ],
                    )
                )

        return findings

    # --- Checks de CI --------------------------------------------------------------

    def _check_findings(
        self, context: AgentContext, signal: dict[str, Any]
    ) -> list[Finding]:
        now = context.now
        repo = str(signal.get("repository") or "desconocido")
        failing = [
            check
            for check in (signal.get("checks") or [])
            if str(check.get("conclusion") or "").lower() in {"failure", "failed", "timed_out"}
        ]
        if not failing:
            return []

        names = ", ".join(str(c.get("name")) for c in failing[:5])
        return [
            self._finding(
                code="failing_checks",
                summary=f"{len(failing)} check(s) fallando en {repo}: {names}.",
                risk_score=WEIGHT_FAILING_CHECKS,
                impact="La rama no está en condiciones de integrarse ni de desplegarse.",
                evidence=[
                    self._evidence(
                        source_type=EvidenceSourceType.GITHUB,
                        provider=PROVIDER,
                        external_id=f"{repo}:{check.get('name')}",
                        source_url=check.get("url"),
                        field="conclusion",
                        value=check.get("conclusion"),
                        observed_at=now,
                        explanation=f"El check '{check.get('name')}' no pasó.",
                    )
                    for check in failing
                ],
            )
        ]

    # --- Calidad -------------------------------------------------------------------

    def _quality_findings(
        self, context: AgentContext, signal: dict[str, Any], missing: list[str]
    ) -> list[Finding]:
        findings: list[Finding] = []
        now = context.now
        repo = str(signal.get("repository") or "desconocido")

        changed = signal.get("changed_files") or []
        if changed:
            touches_tests = any(_looks_like_test(path) for path in changed)
            if not touches_tests:
                findings.append(
                    self._finding(
                        code="no_tests",
                        summary=f"El cambio en {repo} no incluye ninguna prueba.",
                        risk_score=WEIGHT_NO_TESTS,
                        confidence=0.85,
                        impact="Un cambio sin prueba no tiene forma de demostrar que funciona.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.GITHUB,
                                provider=PROVIDER,
                                external_id=repo,
                                field="changed_files",
                                value=f"{len(changed)} ficheros, ninguno de prueba",
                                observed_at=now,
                                explanation="Ningún fichero modificado coincide con un patrón de prueba.",
                            )
                        ],
                    )
                )

        coverage = signal.get("coverage")
        if coverage is None:
            missing.append(
                f"{repo} no reporta cobertura: la suficiencia de las pruebas no se puede verificar."
            )
        elif float(coverage) < COVERAGE_FLOOR:
            findings.append(
                self._finding(
                    code="low_coverage",
                    summary=f"Cobertura de {repo} en {coverage}%, por debajo del mínimo de {COVERAGE_FLOOR}%.",
                    risk_score=WEIGHT_LOW_COVERAGE,
                    impact="Buena parte del código entra a producción sin verificación automática.",
                    evidence=[
                        self._evidence(
                            source_type=EvidenceSourceType.GITHUB,
                            provider=PROVIDER,
                            external_id=repo,
                            field="coverage",
                            value=coverage,
                            observed_at=now,
                            explanation=f"{coverage}% frente al umbral de {COVERAGE_FLOOR}%.",
                        )
                    ],
                )
            )

        return findings

    # --- Migraciones ---------------------------------------------------------------

    def _migration_findings(
        self, context: AgentContext, signal: dict[str, Any]
    ) -> list[Finding]:
        """Detecta migraciones destructivas en los ficheros del cambio.

        Se mira aquí y no en el agente de base de datos porque el hallazgo nace del
        diff: el agente de datos observa el esquema vivo, este observa lo que está a
        punto de aplicarse.
        """
        now = context.now
        repo = str(signal.get("repository") or "desconocido")
        findings: list[Finding] = []

        for migration in signal.get("migrations") or []:
            path = str(migration.get("path") or "")
            content = str(migration.get("content") or "").lower()
            markers = [m for m in DESTRUCTIVE_SQL_MARKERS if m in content]
            has_rollback = bool(migration.get("has_rollback"))

            if markers and not has_rollback:
                findings.append(
                    self._finding(
                        code="risky_migration",
                        summary=f"{path} ejecuta {', '.join(markers)} sin rollback.",
                        risk_score=WEIGHT_RISKY_MIGRATION,
                        impact="Si el despliegue falla, no hay camino de vuelta sin restaurar copia.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.GITHUB,
                                provider=PROVIDER,
                                external_id=f"{repo}:{path}",
                                field="migration",
                                value=", ".join(markers),
                                observed_at=now,
                                explanation="La migración contiene operaciones destructivas y no declara reversión.",
                            )
                        ],
                    )
                )

        return findings

    # --- Acciones ------------------------------------------------------------------

    def _actions(
        self, signal: dict[str, Any], findings: list[Finding]
    ) -> list[RecommendedAction]:
        codes = {f.code for f in findings}
        actions: list[RecommendedAction] = []
        repo = str(signal.get("repository") or "desconocido")

        if "risky_migration" in codes:
            actions.append(
                RecommendedAction(
                    action_type="block_deployment",
                    title=f"Bloquear despliegue de {repo} hasta que la migración sea reversible",
                    rationale="Una migración destructiva sin rollback convierte un fallo de despliegue en pérdida de datos.",
                    payload={"repository": repo, "reason": "risky_migration"},
                    requires_human_approval=True,
                )
            )

        if "failing_checks" in codes or "pr_blocked" in codes:
            actions.append(
                RecommendedAction(
                    action_type="update_jira_issue",
                    title="Reflejar el bloqueo técnico en el elemento de trabajo",
                    rationale="El tablero muestra progreso que el repositorio no respalda.",
                    payload={"repository": repo, "codes": sorted(codes)},
                    requires_human_approval=True,
                )
            )

        return actions


# --- Utilidades --------------------------------------------------------------------


def _as_datetime(value: Any) -> datetime | None:
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


def _looks_like_test(path: Any) -> bool:
    """Reconoce un fichero de prueba por convención de nombre.

    Cubre las convenciones de Python, JS y Go, que son las que aparecen en este
    repositorio y en la mayoría. No pretende ser exhaustivo: un falso negativo produce
    un hallazgo con confianza 0.85, no una afirmación categórica.
    """
    text = str(path).lower()
    return (
        "test" in text
        or "spec" in text
        or text.endswith("_test.go")
        or "/tests/" in text
    )
