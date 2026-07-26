"""Agente de base de datos: riesgo de datos y gobernanza sobre Supabase.

Observa el esquema vivo: si una migración se aplicó sin camino de vuelta, si una tabla
quedó sin RLS, si falta el índice que sostiene una consulta caliente.

Se diferencia del agente de código en el momento que mira. El de código analiza el diff
—lo que está a punto de aplicarse—; este analiza el estado actual. Un esquema puede
estar mal aunque el último PR sea impecable, y un PR puede ser peligroso aunque el
esquema esté sano hoy.

Este agente NUNCA propone SQL ejecutable sin aprobación, y no ejecuta nada. La skill
``database-governance`` recoge la misma regla.
"""

from __future__ import annotations

from typing import Any, ClassVar, Final

from app.agents.specialized.base import AgentContext, BaseSpecializedAgent
from app.schemas.domain import (
    AgentOutput,
    EvidenceSourceType,
    Finding,
    RecommendedAction,
)

PROVIDER: Final[str] = "supabase"

# --- Pesos de las señales ----------------------------------------------------------
# RLS ausente es el peor de los tres: expone datos a cualquiera con la clave pública
# del proyecto, que es pública por definición.
WEIGHT_MISSING_RLS: Final[int] = 90
WEIGHT_MIGRATION_NO_ROLLBACK: Final[int] = 75
WEIGHT_PERMISSIVE_RLS: Final[int] = 70
WEIGHT_MISSING_INDEX: Final[int] = 55
WEIGHT_MISSING_CONSTRAINT: Final[int] = 50
WEIGHT_ORPHAN_ROWS: Final[int] = 45

#: Filas a partir de las cuales una tabla sin índice en su columna de filtrado deja de
#: responder en tiempo aceptable. Por debajo, el escaneo secuencial es más rápido que
#: el índice, así que avisar sería ruido.
INDEX_ROW_THRESHOLD: Final[int] = 10_000


class DatabaseAgent(BaseSpecializedAgent):
    """Analiza el riesgo de datos de un compromiso a partir del esquema de Supabase."""

    name: ClassVar[str] = "database-agent"
    category: ClassVar[str] = "data"

    def analyze(self, context: AgentContext) -> AgentOutput:
        signal = context.signal(PROVIDER)
        if not signal:
            return self._empty_output(
                context,
                [
                    "Sin inspección de esquema: no hay conexión a Supabase para este proyecto. "
                    "No se puede verificar RLS ni reversibilidad de migraciones."
                ],
                reason="No se pudo evaluar el riesgo de datos: falta la señal de Supabase.",
            )

        findings: list[Finding] = []
        missing: list[str] = []

        findings.extend(self._rls_findings(context, signal))
        findings.extend(self._migration_findings(context, signal))
        findings.extend(self._index_findings(context, signal, missing))
        findings.extend(self._integrity_findings(context, signal))

        actions = self._actions(findings)

        return self._output(
            context, findings, missing_information=missing, recommended_actions=actions
        )

    # --- RLS -----------------------------------------------------------------------

    def _rls_findings(
        self, context: AgentContext, signal: dict[str, Any]
    ) -> list[Finding]:
        """Tablas sin RLS o con políticas demasiado abiertas.

        Una tabla sin RLS en Supabase es legible con la clave anónima, que viaja en el
        frontend. No es una mala práctica: es una fuga.
        """
        findings: list[Finding] = []
        now = context.now

        for table in signal.get("tables") or []:
            name = str(table.get("name") or "desconocida")

            if table.get("rls_enabled") is False:
                findings.append(
                    self._finding(
                        code="missing_rls",
                        summary=f"La tabla {name} no tiene Row Level Security activo.",
                        risk_score=WEIGHT_MISSING_RLS,
                        impact="Cualquiera con la clave anónima del proyecto puede leer la tabla.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.SUPABASE,
                                provider=PROVIDER,
                                external_id=name,
                                field="rls_enabled",
                                value=False,
                                observed_at=now,
                                explanation="RLS desactivado expone la tabla a la clave pública.",
                            )
                        ],
                    )
                )
                continue

            permissive = [
                policy
                for policy in (table.get("policies") or [])
                if _is_permissive(policy)
            ]
            if permissive:
                names = ", ".join(str(p.get("name")) for p in permissive)
                findings.append(
                    self._finding(
                        code="permissive_rls",
                        summary=f"{name} tiene política(s) permisiva(s) para anon: {names}.",
                        risk_score=WEIGHT_PERMISSIVE_RLS,
                        impact="RLS está activo pero no restringe: el efecto es el de no tenerlo.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.SUPABASE,
                                provider=PROVIDER,
                                external_id=f"{name}:{policy.get('name')}",
                                field="policy",
                                value=policy.get("definition"),
                                observed_at=now,
                                explanation="La política concede acceso al rol anónimo sin condición.",
                            )
                            for policy in permissive
                        ],
                    )
                )

        return findings

    # --- Migraciones ---------------------------------------------------------------

    def _migration_findings(
        self, context: AgentContext, signal: dict[str, Any]
    ) -> list[Finding]:
        findings: list[Finding] = []
        now = context.now

        for migration in signal.get("migrations") or []:
            name = str(migration.get("name") or migration.get("version") or "desconocida")
            if migration.get("has_rollback") is False:
                findings.append(
                    self._finding(
                        code="migration_no_rollback",
                        summary=f"La migración {name} se aplicó sin script de reversión.",
                        risk_score=WEIGHT_MIGRATION_NO_ROLLBACK,
                        impact="Un fallo en producción obliga a restaurar copia de seguridad.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.SUPABASE,
                                provider=PROVIDER,
                                external_id=name,
                                field="has_rollback",
                                value=False,
                                observed_at=now,
                                explanation="No existe script de reversión asociado a la migración.",
                            )
                        ],
                    )
                )

        return findings

    # --- Índices -------------------------------------------------------------------

    def _index_findings(
        self, context: AgentContext, signal: dict[str, Any], missing: list[str]
    ) -> list[Finding]:
        findings: list[Finding] = []
        now = context.now

        for table in signal.get("tables") or []:
            name = str(table.get("name") or "desconocida")
            row_count = table.get("row_count")

            if row_count is None:
                missing.append(
                    f"No se conoce el número de filas de {name}: "
                    "la necesidad de índices no se puede evaluar."
                )
                continue

            if int(row_count) < INDEX_ROW_THRESHOLD:
                continue

            hot_columns = set(table.get("filtered_columns") or [])
            indexed = set(table.get("indexed_columns") or [])
            unindexed = sorted(hot_columns - indexed)

            if unindexed:
                findings.append(
                    self._finding(
                        code="missing_index",
                        summary=(
                            f"{name} ({row_count} filas) se filtra por "
                            f"{', '.join(unindexed)} sin índice."
                        ),
                        risk_score=WEIGHT_MISSING_INDEX,
                        confidence=0.8,
                        impact="Las consultas degradan a escaneo secuencial conforme crece la tabla.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.SUPABASE,
                                provider=PROVIDER,
                                external_id=name,
                                field="indexed_columns",
                                value=", ".join(sorted(indexed)) or "ninguno",
                                observed_at=now,
                                explanation=(
                                    f"Se filtra por {', '.join(unindexed)} y no hay índice que lo cubra."
                                ),
                            )
                        ],
                    )
                )

        return findings

    # --- Integridad ----------------------------------------------------------------

    def _integrity_findings(
        self, context: AgentContext, signal: dict[str, Any]
    ) -> list[Finding]:
        findings: list[Finding] = []
        now = context.now

        for table in signal.get("tables") or []:
            name = str(table.get("name") or "desconocida")

            if table.get("missing_foreign_keys"):
                columns = ", ".join(str(c) for c in table["missing_foreign_keys"])
                findings.append(
                    self._finding(
                        code="missing_constraint",
                        summary=f"{name} referencia {columns} sin clave ajena declarada.",
                        risk_score=WEIGHT_MISSING_CONSTRAINT,
                        impact="La integridad depende de que la aplicación no se equivoque nunca.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.SUPABASE,
                                provider=PROVIDER,
                                external_id=name,
                                field="missing_foreign_keys",
                                value=columns,
                                observed_at=now,
                                explanation="Columnas con semántica de referencia y sin restricción.",
                            )
                        ],
                    )
                )

            orphans = int(table.get("orphan_rows") or 0)
            if orphans > 0:
                findings.append(
                    self._finding(
                        code="orphan_rows",
                        summary=f"{name} tiene {orphans} fila(s) huérfana(s).",
                        risk_score=WEIGHT_ORPHAN_ROWS,
                        impact="Los agregados que recorren la tabla cuentan datos sin dueño.",
                        evidence=[
                            self._evidence(
                                source_type=EvidenceSourceType.SUPABASE,
                                provider=PROVIDER,
                                external_id=name,
                                field="orphan_rows",
                                value=orphans,
                                observed_at=now,
                                explanation="Filas cuya referencia apunta a un registro inexistente.",
                            )
                        ],
                    )
                )

        return findings

    # --- Acciones ------------------------------------------------------------------

    def _actions(self, findings: list[Finding]) -> list[RecommendedAction]:
        """Acciones propuestas.

        El SQL viaja en el payload como texto para que se pueda leer antes de aprobarlo,
        y nunca se ejecuta desde aquí. Un agente que pudiera aplicar DDL convertiría un
        falso positivo en una incidencia de producción.
        """
        codes = {f.code for f in findings}
        actions: list[RecommendedAction] = []

        if "missing_rls" in codes or "permissive_rls" in codes:
            tables = sorted(
                {
                    ev.external_id
                    for f in findings
                    if f.code in {"missing_rls", "permissive_rls"}
                    for ev in f.evidence
                    if ev.external_id
                }
            )
            actions.append(
                RecommendedAction(
                    action_type="execute_sql",
                    title="Activar RLS en las tablas expuestas",
                    rationale="Una tabla sin RLS es legible con la clave anónima, que viaja en el cliente.",
                    payload={
                        "tables": tables,
                        "sql_preview": [
                            f"alter table public.{t.split(':')[0]} enable row level security;"
                            for t in tables
                        ],
                        "destructive": False,
                    },
                    requires_human_approval=True,
                )
            )

        if "migration_no_rollback" in codes:
            actions.append(
                RecommendedAction(
                    action_type="block_deployment",
                    title="Exigir script de reversión antes del próximo despliegue",
                    rationale="Sin rollback, revertir significa restaurar copia y perder lo escrito desde entonces.",
                    payload={"reason": "migration_no_rollback"},
                    requires_human_approval=True,
                )
            )

        return actions


# --- Utilidades --------------------------------------------------------------------


def _is_permissive(policy: Any) -> bool:
    """Reconoce una política que concede acceso al rol anónimo sin condición.

    Busca ``true`` como expresión de la política junto con el rol ``anon`` o ``public``.
    Una política con ``using (true)`` para ``anon`` deja la tabla abierta: RLS activo y
    sin efecto, que es peor que no tenerlo porque parece protegido.
    """
    if not isinstance(policy, dict):
        return False
    definition = str(policy.get("definition") or "").lower().replace(" ", "")
    roles = str(policy.get("roles") or "").lower()
    grants_all = "using(true)" in definition or definition == "true"
    return grants_all and ("anon" in roles or "public" in roles)
