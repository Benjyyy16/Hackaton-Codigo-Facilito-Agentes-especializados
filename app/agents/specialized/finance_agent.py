"""Agente financiero: exposición económica del compromiso.

No recalcula nada: envuelve ``finance_analysis_service``, que ya hace el cálculo
determinístico con ``Decimal``. La fórmula vive en un solo sitio, y duplicarla aquí
garantizaría que las dos copias divergieran.

Lo que aporta este agente sobre el servicio es la traducción al contrato común: el
servicio devuelve un ``FinanceAnalysis``, y el orquestador necesita un ``AgentOutput``
comparable con el del resto.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar, Final

from app.agents.specialized.base import AgentContext, BaseSpecializedAgent
from app.schemas.domain import AgentOutput, Finding, RecommendedAction
from app.schemas.finance_domain import FinanceSnapshot
from app.services import finance_analysis_service

PROVIDER: Final[str] = "finance"

#: Exposición a partir de la cual la decisión deja de ser técnica. Por encima de este
#: importe la recomendación incluye renegociar alcance, porque absorber el coste ya no
#: es una opción que un equipo pueda tomar por su cuenta.
ESCALATION_EXPOSURE: Final[Decimal] = Decimal("10000")


class FinanceAgent(BaseSpecializedAgent):
    """Traduce el análisis financiero determinístico al contrato de agentes."""

    name: ClassVar[str] = "finance-agent"
    category: ClassVar[str] = "financial"

    def analyze(self, context: AgentContext) -> AgentOutput:
        signal = context.signal(PROVIDER)
        snapshot_data = signal.get("snapshot") if signal else None

        if not snapshot_data:
            return self._empty_output(
                context,
                [
                    "Sin datos financieros: no se importó presupuesto ni horas. "
                    "La exposición económica del compromiso no se puede cuantificar."
                ],
                reason="No se pudo evaluar la exposición económica: falta la señal financiera.",
            )

        try:
            snapshot = (
                snapshot_data
                if isinstance(snapshot_data, FinanceSnapshot)
                else FinanceSnapshot.model_validate(snapshot_data)
            )
        except Exception as error:  # noqa: BLE001 - frontera de validación
            # Un snapshot inválido no es lo mismo que un snapshot ausente: se reporta el
            # motivo para que quien lo importó pueda corregirlo.
            return self._empty_output(
                context,
                [f"Los datos financieros no validan: {type(error).__name__}."],
                reason="No se pudo evaluar la exposición económica: los datos no son válidos.",
            )

        analysis = finance_analysis_service.analyze(snapshot)

        findings: list[Finding] = list(analysis.findings)
        actions = self._actions(analysis.total_exposure, findings)

        summary = (
            f"Exposición total {analysis.total_exposure} {snapshot.currency}: "
            f"penalización {analysis.penalty_exposure}, retenido {analysis.retained_payments}, "
            f"margen {analysis.margin}."
        )

        return self._output(
            context,
            findings,
            summary=summary,
            evidence=list(analysis.evidence),
            recommended_actions=actions,
        )

    def _actions(
        self, total_exposure: Decimal, findings: list[Finding]
    ) -> list[RecommendedAction]:
        """Acciones propuestas. Ninguna se ejecuta sin aprobación.

        En particular, el asiento contable nunca se publica automáticamente: se propone
        con su payload visible para que alguien con responsabilidad contable lo revise.
        """
        codes = {f.code for f in findings}
        actions: list[RecommendedAction] = []

        if total_exposure > ESCALATION_EXPOSURE:
            actions.append(
                RecommendedAction(
                    action_type="renegotiate_scope",
                    title="Renegociar alcance o fecha con el beneficiario",
                    rationale=(
                        f"La exposición ({total_exposure}) supera el umbral de escalado "
                        f"({ESCALATION_EXPOSURE}): absorber el coste ya no es una decisión de equipo."
                    ),
                    payload={"total_exposure": str(total_exposure)},
                    requires_human_approval=True,
                )
            )

        if "penalty_exposure" in codes:
            actions.append(
                RecommendedAction(
                    action_type="post_accounting_entry",
                    title="Provisionar la penalización contractual",
                    rationale=(
                        "La probabilidad de incurrir en la penalización justifica reconocer "
                        "una provisión. Requiere validación contable: moneda funcional, "
                        "periodo y cuenta destino no los decide el sistema."
                    ),
                    payload={
                        "entry_type": "provision",
                        "requires_validation": [
                            "moneda_funcional",
                            "politica_contable",
                            "periodo",
                            "cuentas_contables",
                            "regla_de_aprobacion",
                        ],
                    },
                    requires_human_approval=True,
                )
            )

        return actions
