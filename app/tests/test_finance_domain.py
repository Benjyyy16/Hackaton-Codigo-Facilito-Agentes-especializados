"""Tests del dominio financiero.

Cubren: validación de schemas, carga JSON/CSV, cálculos determinísticos, findings
condicionales y reproducibilidad del seed demo. Cada test es hermético y usa valores
exactos en Decimal para evitar problemas de representación binaria.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.providers.finance import FinanceProvider
from app.schemas.domain import EvidenceSourceType, Severity
from app.schemas.finance_domain import (
    BudgetLine,
    LaborEntry,
    Penalty,
)
from app.services.finance_analysis_service import analyze

# ---------------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------------

SEED_PATH = Path(__file__).resolve().parents[2] / "db" / "seed" / "finance_seed.json"


@pytest.fixture
def provider() -> FinanceProvider:
    return FinanceProvider()


@pytest.fixture
def seed_data() -> dict:
    return json.loads(SEED_PATH.read_text())


@pytest.fixture
def minimal_snapshot_data() -> dict:
    """Snapshot mínimo válido: 1 budget line, sin labor ni penalties."""
    return {
        "project_key": "TEST",
        "commitment_ref": "Compromiso de prueba",
        "currency": "USD",
        "budget_lines": [
            {"concept": "Desarrollo", "planned": "10000", "actual": "5000"}
        ],
        "period_start": "2026-07-01",
        "period_end": "2026-07-10",
    }


@pytest.fixture
def full_snapshot_data() -> dict:
    """Snapshot con todos los campos para tests de cálculo."""
    return {
        "project_key": "CALC",
        "commitment_ref": "Test cálculos",
        "currency": "USD",
        "budget_lines": [
            {"concept": "A", "planned": "20000", "actual": "15000"},
            {"concept": "B", "planned": "10000", "actual": "8000"},
        ],
        "labor_entries": [
            {"role": "Dev", "hours": "80", "hourly_rate": "50", "date": "2026-07-01"},
            {"role": "QA", "hours": "40", "hourly_rate": "40", "date": "2026-07-01"},
        ],
        "penalties": [
            {
                "description": "Retraso",
                "amount": "5000",
                "trigger_condition": "No entregar",
                "probability": 0.5,
            }
        ],
        "retained_payments": "3000",
        "period_start": "2026-07-01",
        "period_end": "2026-07-11",
    }


# ---------------------------------------------------------------------------------
# 1. Carga JSON válida
# ---------------------------------------------------------------------------------


class TestJsonLoading:
    def test_load_minimal_json(self, provider: FinanceProvider, minimal_snapshot_data: dict):
        snap = provider.load_from_json(minimal_snapshot_data)
        assert snap.project_key == "TEST"
        assert len(snap.budget_lines) == 1
        assert snap.budget_lines[0].planned == Decimal("10000")

    def test_load_seed_json(self, provider: FinanceProvider, seed_data: dict):
        snap = provider.load_from_json(seed_data)
        assert snap.commitment_ref == "Entregar integración de pagos empresariales antes del viernes"
        assert len(snap.budget_lines) == 4
        assert len(snap.penalties) == 1
        assert snap.penalties[0].amount == Decimal("20000")

    def test_load_full_json(self, provider: FinanceProvider, full_snapshot_data: dict):
        snap = provider.load_from_json(full_snapshot_data)
        assert snap.retained_payments == Decimal("3000")
        assert len(snap.labor_entries) == 2


# ---------------------------------------------------------------------------------
# 2. Carga JSON inválida
# ---------------------------------------------------------------------------------


class TestJsonInvalid:
    def test_missing_budget_lines(self, provider: FinanceProvider):
        with pytest.raises(ValidationError):
            provider.load_from_json({
                "project_key": "X",
                "commitment_ref": "ref",
                "period_start": "2026-01-01",
                "period_end": "2026-01-10",
                "budget_lines": [],
            })

    def test_missing_project_key(self, provider: FinanceProvider):
        with pytest.raises(ValidationError):
            provider.load_from_json({
                "commitment_ref": "ref",
                "budget_lines": [{"concept": "A", "planned": "100", "actual": "50"}],
                "period_start": "2026-01-01",
                "period_end": "2026-01-10",
            })

    def test_float_in_budget_planned_rejected(self, provider: FinanceProvider):
        """Float explícito en campo monetario debe ser rechazado."""
        with pytest.raises(ValidationError):
            provider.load_from_json({
                "project_key": "X",
                "commitment_ref": "ref",
                "budget_lines": [{"concept": "A", "planned": 100.5, "actual": "50"}],
                "period_start": "2026-01-01",
                "period_end": "2026-01-10",
            })


# ---------------------------------------------------------------------------------
# 3. Carga CSV válida
# ---------------------------------------------------------------------------------


VALID_CSV = """[META]
project_key,commitment_ref,currency,retained_payments,period_start,period_end
CSV-PRJ,Compromiso CSV,USD,1000,2026-07-01,2026-07-10
[BUDGET]
concept,planned,actual,currency,category
Desarrollo,8000,6000,USD,dev
QA,4000,3000,USD,calidad
[LABOR]
role,hours,hourly_rate,date
Dev,40,60,2026-07-01
[PENALTIES]
description,amount,trigger_condition,probability
Multa,3000,Retraso entrega,0.7
"""


class TestCsvLoading:
    def test_load_valid_csv(self, provider: FinanceProvider):
        snap = provider.load_from_csv(VALID_CSV)
        assert snap.project_key == "CSV-PRJ"
        assert len(snap.budget_lines) == 2
        assert snap.budget_lines[0].planned == Decimal("8000")
        assert len(snap.labor_entries) == 1
        assert snap.penalties[0].probability == 0.7

    def test_csv_without_optional_sections(self, provider: FinanceProvider):
        csv_minimal = """[META]
project_key,commitment_ref,currency,retained_payments,period_start,period_end
MIN,Minimal,USD,0,2026-07-01,2026-07-05
[BUDGET]
concept,planned,actual
Unica,5000,2000
"""
        snap = provider.load_from_csv(csv_minimal)
        assert len(snap.labor_entries) == 0
        assert len(snap.penalties) == 0


# ---------------------------------------------------------------------------------
# 4. Carga CSV inválida
# ---------------------------------------------------------------------------------


class TestCsvInvalid:
    def test_csv_missing_meta(self, provider: FinanceProvider):
        bad_csv = """[BUDGET]
concept,planned,actual
A,100,50
"""
        with pytest.raises(ValueError, match="META"):
            provider.load_from_csv(bad_csv)

    def test_csv_missing_budget(self, provider: FinanceProvider):
        bad_csv = """[META]
project_key,commitment_ref,currency,retained_payments,period_start,period_end
X,ref,USD,0,2026-01-01,2026-01-10
"""
        with pytest.raises((ValueError, ValidationError)):
            provider.load_from_csv(bad_csv)

    def test_csv_malformed_date(self, provider: FinanceProvider):
        bad_csv = """[META]
project_key,commitment_ref,currency,retained_payments,period_start,period_end
X,ref,USD,0,not-a-date,2026-01-10
[BUDGET]
concept,planned,actual
A,100,50
"""
        with pytest.raises((ValueError, ValidationError)):
            provider.load_from_csv(bad_csv)


# ---------------------------------------------------------------------------------
# 5. Cálculos determinísticos con valores exactos
# ---------------------------------------------------------------------------------


class TestCalculations:
    def test_variance_calculation(self, provider: FinanceProvider, full_snapshot_data: dict):
        snap = provider.load_from_json(full_snapshot_data)
        analysis = analyze(snap)
        # total_actual(15000+8000=23000) - total_planned(20000+10000=30000) = -7000
        assert analysis.variance == Decimal("-7000.00")

    def test_variance_pct(self, provider: FinanceProvider, full_snapshot_data: dict):
        snap = provider.load_from_json(full_snapshot_data)
        analysis = analyze(snap)
        # -7000 / 30000 * 100 = -23.33...
        assert analysis.variance_pct == Decimal("-23.33")

    def test_labor_cost(self, provider: FinanceProvider, full_snapshot_data: dict):
        snap = provider.load_from_json(full_snapshot_data)
        analysis = analyze(snap)
        # 80*50 + 40*40 = 4000 + 1600 = 5600
        assert analysis.labor_cost == Decimal("5600.00")

    def test_margin(self, provider: FinanceProvider, full_snapshot_data: dict):
        snap = provider.load_from_json(full_snapshot_data)
        analysis = analyze(snap)
        # 30000 - 23000 - 5600 = 1400
        assert analysis.margin == Decimal("1400.00")

    def test_burn_rate_daily(self, provider: FinanceProvider, full_snapshot_data: dict):
        snap = provider.load_from_json(full_snapshot_data)
        analysis = analyze(snap)
        # 23000 / 10 días = 2300
        assert analysis.burn_rate_daily == Decimal("2300.00")

    def test_penalty_exposure(self, provider: FinanceProvider, full_snapshot_data: dict):
        snap = provider.load_from_json(full_snapshot_data)
        analysis = analyze(snap)
        # 5000 * 0.5 = 2500
        assert analysis.penalty_exposure == Decimal("2500.00")

    def test_total_exposure(self, provider: FinanceProvider, full_snapshot_data: dict):
        snap = provider.load_from_json(full_snapshot_data)
        analysis = analyze(snap)
        # penalty_exposure(2500) + retained(3000) + max(0, -margin=max(0,-1400)=0) = 5500
        assert analysis.total_exposure == Decimal("5500.00")

    def test_burn_rate_zero_days(self, provider: FinanceProvider):
        """Periodo de 0 días no debe causar división por cero."""
        data = {
            "project_key": "ZERO",
            "commitment_ref": "Zero period",
            "budget_lines": [{"concept": "A", "planned": "1000", "actual": "500"}],
            "period_start": "2026-07-10",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        assert analysis.burn_rate_daily == Decimal("0")


# ---------------------------------------------------------------------------------
# 6. Findings condicionales: se disparan cuando deben
# ---------------------------------------------------------------------------------


class TestFindingsTriggered:
    def test_budget_overrun_fires(self, provider: FinanceProvider):
        """Cuando actual > planned, debe existir finding budget_overrun."""
        data = {
            "project_key": "OVR",
            "commitment_ref": "Overrun",
            "budget_lines": [{"concept": "A", "planned": "1000", "actual": "1500"}],
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        codes = [f.code for f in analysis.findings]
        assert "budget_overrun" in codes

    def test_negative_margin_fires(self, provider: FinanceProvider):
        """Margen negativo produce finding negative_margin."""
        data = {
            "project_key": "NEG",
            "commitment_ref": "Negative",
            "budget_lines": [{"concept": "A", "planned": "1000", "actual": "800"}],
            "labor_entries": [
                {"role": "Dev", "hours": "10", "hourly_rate": "50", "date": "2026-07-01"}
            ],
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        # margin = 1000 - 800 - 500 = -300
        codes = [f.code for f in analysis.findings]
        assert "negative_margin" in codes

    def test_penalty_exposure_fires(self, provider: FinanceProvider):
        data = {
            "project_key": "PEN",
            "commitment_ref": "Penalty",
            "budget_lines": [{"concept": "A", "planned": "10000", "actual": "5000"}],
            "penalties": [
                {"description": "Multa", "amount": "5000", "trigger_condition": "Retraso", "probability": 0.8}
            ],
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        codes = [f.code for f in analysis.findings]
        assert "penalty_exposure" in codes

    def test_overtime_projected_fires(self, provider: FinanceProvider):
        """Horas totales superando 8h * días del periodo dispara overtime."""
        data = {
            "project_key": "OT",
            "commitment_ref": "Overtime",
            "budget_lines": [{"concept": "A", "planned": "10000", "actual": "5000"}],
            "labor_entries": [
                {"role": "Dev", "hours": "100", "hourly_rate": "50", "date": "2026-07-01"}
            ],
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        # standard = 8 * 9 = 72h, actual = 100h => overtime = 28h
        codes = [f.code for f in analysis.findings]
        assert "overtime_projected" in codes

    def test_retained_payment_risk_fires(self, provider: FinanceProvider):
        data = {
            "project_key": "RET",
            "commitment_ref": "Retained",
            "budget_lines": [{"concept": "A", "planned": "10000", "actual": "5000"}],
            "retained_payments": "2000",
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        # 2000 > 10000 * 0.10 = 1000 => fires
        codes = [f.code for f in analysis.findings]
        assert "retained_payment_risk" in codes


# ---------------------------------------------------------------------------------
# 7. Findings condicionales: NO se disparan cuando no deben
# ---------------------------------------------------------------------------------


class TestFindingsNotTriggered:
    def test_no_budget_overrun_when_under_plan(self, provider: FinanceProvider):
        data = {
            "project_key": "OK",
            "commitment_ref": "Under plan",
            "budget_lines": [{"concept": "A", "planned": "10000", "actual": "5000"}],
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        codes = [f.code for f in analysis.findings]
        assert "budget_overrun" not in codes

    def test_no_negative_margin_when_positive(self, provider: FinanceProvider):
        data = {
            "project_key": "OK",
            "commitment_ref": "Positive margin",
            "budget_lines": [{"concept": "A", "planned": "10000", "actual": "3000"}],
            "labor_entries": [
                {"role": "Dev", "hours": "10", "hourly_rate": "50", "date": "2026-07-01"}
            ],
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        # margin = 10000 - 3000 - 500 = 6500
        codes = [f.code for f in analysis.findings]
        assert "negative_margin" not in codes

    def test_no_penalty_when_none_defined(self, provider: FinanceProvider):
        data = {
            "project_key": "OK",
            "commitment_ref": "No penalties",
            "budget_lines": [{"concept": "A", "planned": "10000", "actual": "5000"}],
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        codes = [f.code for f in analysis.findings]
        assert "penalty_exposure" not in codes

    def test_no_overtime_when_under_standard(self, provider: FinanceProvider):
        data = {
            "project_key": "OK",
            "commitment_ref": "Normal hours",
            "budget_lines": [{"concept": "A", "planned": "10000", "actual": "5000"}],
            "labor_entries": [
                {"role": "Dev", "hours": "20", "hourly_rate": "50", "date": "2026-07-01"}
            ],
            "period_start": "2026-07-01",
            "period_end": "2026-07-10",
        }
        snap = provider.load_from_json(data)
        analysis = analyze(snap)
        # standard = 8*9=72, hours=20 < 72
        codes = [f.code for f in analysis.findings]
        assert "overtime_projected" not in codes


# ---------------------------------------------------------------------------------
# 8. Seed demo produce severidad alta o crítica (reproducibilidad)
# ---------------------------------------------------------------------------------


class TestSeedReproducibility:
    def test_seed_produces_high_or_critical(self, provider: FinanceProvider, seed_data: dict):
        snap = provider.load_from_json(seed_data)
        analysis = analyze(snap)
        severities = {f.severity for f in analysis.findings}
        assert severities & {Severity.HIGH, Severity.CRITICAL}, (
            f"El seed debe producir al menos un finding HIGH o CRITICAL, got: {severities}"
        )

    def test_seed_has_penalty_finding(self, provider: FinanceProvider, seed_data: dict):
        snap = provider.load_from_json(seed_data)
        analysis = analyze(snap)
        codes = [f.code for f in analysis.findings]
        assert "penalty_exposure" in codes

    def test_seed_deterministic(self, provider: FinanceProvider, seed_data: dict):
        """Dos ejecuciones con el mismo input producen el mismo resultado numérico."""
        snap = provider.load_from_json(seed_data)
        a1 = analyze(snap)
        a2 = analyze(snap)
        assert a1.total_exposure == a2.total_exposure
        assert a1.variance == a2.variance
        assert a1.margin == a2.margin
        assert len(a1.findings) == len(a2.findings)


# ---------------------------------------------------------------------------------
# 9. No se usa float en campos monetarios
# ---------------------------------------------------------------------------------


class TestNoFloatInMoney:
    def test_budget_line_rejects_float_planned(self):
        with pytest.raises(ValidationError):
            BudgetLine(concept="X", planned=100.5, actual=Decimal("50"))  # type: ignore[arg-type]

    def test_budget_line_rejects_float_actual(self):
        with pytest.raises(ValidationError):
            BudgetLine(concept="X", planned=Decimal("100"), actual=50.5)  # type: ignore[arg-type]

    def test_labor_entry_rejects_float_rate(self):
        with pytest.raises(ValidationError):
            LaborEntry(role="Dev", hours=Decimal("8"), hourly_rate=50.0, date=date(2026, 7, 1))  # type: ignore[arg-type]

    def test_penalty_rejects_float_amount(self):
        with pytest.raises(ValidationError):
            Penalty(description="X", amount=1000.0, trigger_condition="cond", probability=0.5)  # type: ignore[arg-type]

    def test_analysis_fields_are_decimal(self, provider: FinanceProvider, seed_data: dict):
        snap = provider.load_from_json(seed_data)
        analysis = analyze(snap)
        money_fields = [
            analysis.total_planned, analysis.total_actual, analysis.variance,
            analysis.labor_cost, analysis.margin, analysis.burn_rate_daily,
            analysis.penalty_exposure, analysis.retained_payments, analysis.total_exposure,
        ]
        for field in money_fields:
            assert isinstance(field, Decimal), f"Expected Decimal, got {type(field)}"


# ---------------------------------------------------------------------------------
# 10. Evidence
# ---------------------------------------------------------------------------------


class TestEvidence:
    def test_get_evidence_returns_finance_source(self, provider: FinanceProvider, seed_data: dict):
        snap = provider.load_from_json(seed_data)
        evidences = provider.get_evidence(snap)
        assert len(evidences) > 0
        for ev in evidences:
            assert ev.source_type == EvidenceSourceType.FINANCE

    def test_findings_have_evidence(self, provider: FinanceProvider, seed_data: dict):
        snap = provider.load_from_json(seed_data)
        analysis = analyze(snap)
        for finding in analysis.findings:
            assert len(finding.evidence) > 0, f"Finding {finding.code} sin evidencia"


# ---------------------------------------------------------------------------------
# 11. Provider health
# ---------------------------------------------------------------------------------


class TestProviderHealth:
    @pytest.mark.anyio
    async def test_health_before_connect(self):
        p = FinanceProvider()
        h = await p.health()
        assert h.status.value == "unknown"

    @pytest.mark.anyio
    async def test_health_after_connect(self):
        p = FinanceProvider()
        await p.connect()
        h = await p.health()
        assert h.status.value == "up"

    @pytest.mark.anyio
    async def test_health_after_close(self):
        p = FinanceProvider()
        await p.connect()
        await p.close()
        h = await p.health()
        assert h.status.value == "unknown"
