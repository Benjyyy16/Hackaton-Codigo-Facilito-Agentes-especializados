"""Modelos del dominio financiero de Datgent.

Separados de ``finance.py`` (que describe la conexión al ERP) porque aquí se modela el
**análisis** del compromiso, no la integración. La razón de usar Decimal y no float: el
dinero se representa en base 10 y las operaciones deben ser reproducibles bit a bit; un
centavo de error de redondeo en un hallazgo destruye la confianza del auditor.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.domain import Evidence, Finding


# ---------------------------------------------------------------------------------
# Primitivas financieras
# ---------------------------------------------------------------------------------

#: Importe estricto: Decimal, sin restricción de signo porque varianza y margen pueden
#: ser negativos. No es ``Money`` del dominio (que fuerza ≥0).
Amount = Annotated[Decimal, Field(description="Importe monetario en Decimal.")]


class BudgetLine(BaseModel):
    """Línea presupuestaria individual.

    Se modela por línea y no como totales porque el agente necesita señalar *cuál*
    partida se desvió, no solo que el presupuesto global está mal.
    """

    model_config = ConfigDict(frozen=True)

    concept: str = Field(min_length=1, max_length=200)
    planned: Decimal = Field(description="Monto planificado.")
    actual: Decimal = Field(description="Monto ejecutado a la fecha.")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    category: str = Field(default="general", max_length=100)

    @field_validator("planned", "actual", mode="before")
    @classmethod
    def _coerce_to_decimal(cls, v: object) -> Decimal:
        """Acepta strings y enteros, rechaza float explícitamente en runtime."""
        if isinstance(v, float):
            # Se rechaza float porque la pérdida de precisión ya ocurrió al construirlo.
            raise ValueError("float no permitido para campos monetarios; usar str o Decimal")
        return Decimal(str(v))


class LaborEntry(BaseModel):
    """Registro de horas trabajadas.

    Separado del presupuesto porque las horas son la variable que más rápido cambia y
    la más difícil de recuperar: un gasto se puede recortar, las horas ya invertidas no.
    """

    model_config = ConfigDict(frozen=True)

    role: str = Field(min_length=1, max_length=100)
    hours: Decimal = Field(ge=0)
    hourly_rate: Decimal = Field(ge=0)
    date: date

    @field_validator("hours", "hourly_rate", mode="before")
    @classmethod
    def _coerce_to_decimal(cls, v: object) -> Decimal:
        if isinstance(v, float):
            raise ValueError("float no permitido para campos monetarios; usar str o Decimal")
        return Decimal(str(v))


class Penalty(BaseModel):
    """Penalización contractual potencial.

    ``probability`` es float porque es una estimación subjetiva (0-1), no un importe
    contable. El producto amount*probability sí se convierte a Decimal para operar.
    """

    model_config = ConfigDict(frozen=True)

    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(ge=0)
    trigger_condition: str = Field(min_length=1, max_length=500)
    probability: float = Field(ge=0.0, le=1.0)

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_to_decimal(cls, v: object) -> Decimal:
        if isinstance(v, float):
            raise ValueError("float no permitido para campos monetarios; usar str o Decimal")
        return Decimal(str(v))


# ---------------------------------------------------------------------------------
# Snapshot: foto completa del estado financiero del compromiso
# ---------------------------------------------------------------------------------


class FinanceSnapshot(BaseModel):
    """Estado financiero completo de un compromiso en un periodo.

    Es la entrada del servicio de análisis. Se construye desde JSON o CSV mediante el
    provider, y una vez creada es inmutable: el análisis opera sobre una foto fija.
    """

    model_config = ConfigDict(frozen=True)

    project_key: str = Field(min_length=1, max_length=100)
    commitment_ref: str = Field(min_length=1, max_length=300)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    budget_lines: list[BudgetLine] = Field(min_length=1)
    labor_entries: list[LaborEntry] = Field(default_factory=list)
    penalties: list[Penalty] = Field(default_factory=list)
    retained_payments: Decimal = Field(default=Decimal("0"), ge=0)
    period_start: date
    period_end: date

    @field_validator("retained_payments", mode="before")
    @classmethod
    def _coerce_to_decimal(cls, v: object) -> Decimal:
        if isinstance(v, float):
            raise ValueError("float no permitido para campos monetarios; usar str o Decimal")
        return Decimal(str(v))


# ---------------------------------------------------------------------------------
# Resultado del análisis
# ---------------------------------------------------------------------------------


class FinanceAnalysis(BaseModel):
    """Resultado determinístico del análisis financiero.

    Todos los campos monetarios son Decimal quantizado a 2 decimales. Los findings y
    evidence permiten al orquestador correlacionar con los otros agentes.
    """

    model_config = ConfigDict(frozen=True)

    total_planned: Decimal
    total_actual: Decimal
    variance: Decimal
    variance_pct: Decimal
    labor_cost: Decimal
    margin: Decimal
    margin_pct: Decimal
    burn_rate_daily: Decimal
    penalty_exposure: Decimal
    retained_payments: Decimal
    total_exposure: Decimal
    overtime_hours_projected: Decimal
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


# ---------------------------------------------------------------------------------
# Request/Report para la API de importación
# ---------------------------------------------------------------------------------


class FinanceImportRequest(BaseModel):
    """Petición de importación de datos financieros.

    Soporta JSON inline o contenido CSV como string. Solo uno de los dos debe estar
    presente; si ambos llegan, se prefiere ``json_data`` porque es más rico.
    """

    project_key: str = Field(min_length=1, max_length=100)
    commitment_ref: str = Field(min_length=1, max_length=300)
    json_data: dict | None = Field(default=None)
    csv_content: str | None = Field(default=None)


class FinanceImportReport(BaseModel):
    """Resultado de una importación de datos financieros."""

    success: bool
    snapshot: FinanceSnapshot | None = None
    analysis: FinanceAnalysis | None = None
    errors: list[str] = Field(default_factory=list)
