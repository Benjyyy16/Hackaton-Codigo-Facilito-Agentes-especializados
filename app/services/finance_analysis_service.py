"""Servicio de análisis financiero determinístico.

Las fórmulas son fijas y auditables: dado el mismo snapshot, el resultado es siempre
idéntico bit a bit. No hay aleatoriedad, no hay heurísticas del LLM, no hay redondeo
implícito. Esto permite que el orquestador compare ejecuciones y que un auditor
reproduzca el cálculo a mano.

Todos los importes se quantizan a 2 decimales con ROUND_HALF_UP, que es el redondeo
contable estándar (no el bancario). La razón: consistencia con lo que espera el CFO.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from app.schemas.domain import (
    Evidence,
    EvidenceSourceType,
    Finding,
    severity_for_score,
)
from app.schemas.finance_domain import FinanceAnalysis, FinanceSnapshot

#: Quantizador a 2 decimales, reutilizado en todo el módulo.
_Q2 = Decimal("0.01")

#: Horas estándar por día laborable. Se usa para proyectar overtime.
_STANDARD_HOURS_PER_DAY = Decimal("8")


def _q(value: Decimal) -> Decimal:
    """Quantiza a 2 decimales con redondeo contable."""
    return value.quantize(_Q2, rounding=ROUND_HALF_UP)


def analyze(snapshot: FinanceSnapshot) -> FinanceAnalysis:
    """Ejecuta el análisis financiero completo sobre un snapshot.

    Cada cálculo está en su propia sección para facilitar la auditoría. Los findings se
    generan condicionalmente: solo aparecen si la condición de riesgo se cumple.
    """
    now = datetime.now(UTC)

    # --- Totales presupuestarios ---
    total_planned = _q(sum((bl.planned for bl in snapshot.budget_lines), Decimal("0")))
    total_actual = _q(sum((bl.actual for bl in snapshot.budget_lines), Decimal("0")))

    # --- Varianza: positivo = sobrecosto ---
    variance = _q(total_actual - total_planned)
    variance_pct = _q(
        (variance / total_planned * Decimal("100")) if total_planned != 0 else Decimal("0")
    )

    # --- Costo laboral ---
    labor_cost = _q(
        sum((le.hours * le.hourly_rate for le in snapshot.labor_entries), Decimal("0"))
    )

    # --- Margen: lo que queda después de pagar ejecución + labor ---
    margin = _q(total_planned - total_actual - labor_cost)
    margin_pct = _q(
        (margin / total_planned * Decimal("100")) if total_planned != 0 else Decimal("0")
    )

    # --- Burn rate diario ---
    period_days = (snapshot.period_end - snapshot.period_start).days
    burn_rate_daily = _q(total_actual / Decimal(period_days)) if period_days > 0 else Decimal("0")

    # --- Exposición por penalizaciones ---
    penalty_exposure = _q(
        sum(
            (Decimal(str(p.probability)) * p.amount for p in snapshot.penalties),
            Decimal("0"),
        )
    )

    # --- Pagos retenidos ---
    retained = _q(snapshot.retained_payments)

    # --- Exposición total: penalizaciones + retenciones + margen negativo absorbido ---
    negative_margin_component = max(Decimal("0"), -margin)
    total_exposure = _q(penalty_exposure + retained + negative_margin_component)

    # --- Horas extra proyectadas ---
    total_hours = sum((le.hours for le in snapshot.labor_entries), Decimal("0"))
    standard_hours = _STANDARD_HOURS_PER_DAY * Decimal(max(period_days, 1))
    overtime_hours_projected = _q(max(Decimal("0"), total_hours - standard_hours))

    # ---------------------------------------------------------------------------------
    # Findings: cada uno con su evidencia y severidad derivada del score
    # ---------------------------------------------------------------------------------
    findings: list[Finding] = []
    all_evidence: list[Evidence] = []

    # 1. budget_overrun: varianza positiva (se gastó más de lo planeado)
    if variance > 0:
        score = min(100, int(abs(variance_pct)))
        sev = severity_for_score(score)
        ev = Evidence(
            source_type=EvidenceSourceType.FINANCE,
            provider="finance",
            field="variance",
            value=str(variance),
            observed_at=now,
            explanation=f"Sobrecosto de {variance} ({variance_pct}% sobre plan)",
        )
        findings.append(
            Finding(
                category="financial",
                code="budget_overrun",
                severity=sev,
                risk_score=score,
                confidence=1.0,
                summary=f"Presupuesto excedido en {variance_pct}%",
                impact=f"Sobrecosto acumulado de {variance} {snapshot.currency}",
                evidence=[ev],
            )
        )
        all_evidence.append(ev)

    # 2. negative_margin: margen negativo indica que el proyecto pierde dinero
    if margin < 0:
        score = min(100, int(abs(margin_pct)))
        sev = severity_for_score(score)
        ev = Evidence(
            source_type=EvidenceSourceType.FINANCE,
            provider="finance",
            field="margin",
            value=str(margin),
            observed_at=now,
            explanation=f"Margen negativo: {margin} ({margin_pct}% del plan)",
        )
        findings.append(
            Finding(
                category="financial",
                code="negative_margin",
                severity=sev,
                risk_score=score,
                confidence=1.0,
                summary=f"Margen negativo de {margin_pct}%",
                impact=f"Pérdida proyectada de {abs(margin)} {snapshot.currency}",
                evidence=[ev],
            )
        )
        all_evidence.append(ev)

    # 3. high_burn_rate: burn rate > planned/days * 1.2 (20% sobre ritmo ideal)
    if period_days > 0 and total_planned > 0:
        ideal_daily = total_planned / Decimal(period_days)
        if burn_rate_daily > ideal_daily * Decimal("1.2"):
            ratio = int((burn_rate_daily / ideal_daily - 1) * 100)
            score = min(100, 40 + ratio)
            sev = severity_for_score(score)
            ev = Evidence(
                source_type=EvidenceSourceType.FINANCE,
                provider="finance",
                field="burn_rate_daily",
                value=str(burn_rate_daily),
                observed_at=now,
                explanation=(
                    f"Ritmo de gasto {burn_rate_daily}/día vs ideal {_q(ideal_daily)}/día "
                    f"(+{ratio}%)"
                ),
            )
            findings.append(
                Finding(
                    category="financial",
                    code="high_burn_rate",
                    severity=sev,
                    risk_score=score,
                    confidence=1.0,
                    summary=f"Burn rate {ratio}% sobre el ritmo ideal",
                    impact="El presupuesto se agotará antes del cierre del periodo",
                    evidence=[ev],
                )
            )
            all_evidence.append(ev)

    # 4. penalty_exposure: hay penalizaciones con exposición > 0
    if penalty_exposure > 0:
        # Score proporcional al peso de la penalización vs presupuesto total
        pct = int(penalty_exposure / total_planned * 100) if total_planned > 0 else 80
        score = min(100, max(40, pct))
        sev = severity_for_score(score)
        ev = Evidence(
            source_type=EvidenceSourceType.FINANCE,
            provider="finance",
            field="penalty_exposure",
            value=str(penalty_exposure),
            observed_at=now,
            explanation=f"Exposición esperada por penalizaciones: {penalty_exposure} {snapshot.currency}",
        )
        findings.append(
            Finding(
                category="financial",
                code="penalty_exposure",
                severity=sev,
                risk_score=score,
                confidence=0.85,
                summary=f"Penalizaciones exponen {penalty_exposure} {snapshot.currency}",
                impact="Pérdida contractual si se incumplen condiciones",
                evidence=[ev],
            )
        )
        all_evidence.append(ev)

    # 5. retained_payment_risk: pagos retenidos significativos (>10% del plan)
    if total_planned > 0 and retained > total_planned * Decimal("0.10"):
        pct_retained = int(retained / total_planned * 100)
        score = min(100, 30 + pct_retained)
        sev = severity_for_score(score)
        ev = Evidence(
            source_type=EvidenceSourceType.FINANCE,
            provider="finance",
            field="retained_payments",
            value=str(retained),
            observed_at=now,
            explanation=f"Pagos retenidos: {retained} ({pct_retained}% del presupuesto)",
        )
        findings.append(
            Finding(
                category="financial",
                code="retained_payment_risk",
                severity=sev,
                risk_score=score,
                confidence=0.9,
                summary=f"Retención del {pct_retained}% compromete liquidez",
                impact="Flujo de caja insuficiente para cubrir obligaciones inmediatas",
                evidence=[ev],
            )
        )
        all_evidence.append(ev)

    # 6. overtime_projected: horas extra proyectadas > 0
    if overtime_hours_projected > 0:
        # Score basado en proporción de overtime vs standard
        ot_ratio = int(overtime_hours_projected / standard_hours * 100) if standard_hours > 0 else 50
        score = min(100, 30 + ot_ratio)
        sev = severity_for_score(score)
        ev = Evidence(
            source_type=EvidenceSourceType.FINANCE,
            provider="finance",
            field="overtime_hours_projected",
            value=str(overtime_hours_projected),
            observed_at=now,
            explanation=f"Horas extra proyectadas: {overtime_hours_projected}h sobre {standard_hours}h estándar",
        )
        findings.append(
            Finding(
                category="financial",
                code="overtime_projected",
                severity=sev,
                risk_score=score,
                confidence=0.75,
                summary=f"Se proyectan {overtime_hours_projected}h extra",
                impact="Incremento de costos laborales y riesgo de agotamiento del equipo",
                evidence=[ev],
            )
        )
        all_evidence.append(ev)

    return FinanceAnalysis(
        total_planned=total_planned,
        total_actual=total_actual,
        variance=variance,
        variance_pct=variance_pct,
        labor_cost=labor_cost,
        margin=margin,
        margin_pct=margin_pct,
        burn_rate_daily=burn_rate_daily,
        penalty_exposure=penalty_exposure,
        retained_payments=retained,
        total_exposure=total_exposure,
        overtime_hours_projected=overtime_hours_projected,
        findings=findings,
        evidence=all_evidence,
    )
