"""Contratos del análisis de riesgo.

Se declaran en `schemas/` y no en `agents/` porque los usan tanto los agentes como los
servicios y la API. Los agentes dependen de estos tipos; los tipos no dependen de nada.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StrEnum

#: Tramos de severidad. El umbral de alerta es configurable y es independiente de estos
#: tramos: la severidad describe la gravedad, el umbral decide si se avisa.
SEVERITY_MEDIUM_FLOOR: Final[int] = 40
SEVERITY_HIGH_FLOOR: Final[int] = 60
SEVERITY_CRITICAL_FLOOR: Final[int] = 80

RiskScore = Annotated[int, Field(ge=0, le=100)]


class Severity(StrEnum):
    """Gravedad de un análisis o de una alerta.

    Los valores coinciden con la restricción ``check`` de las tablas ``risk_analyses`` y
    ``alerts``.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CommitmentStatus(StrEnum):
    """Estado de un compromiso, según la restricción de ``commitments.status``."""

    OPEN = "open"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    MET = "met"


def severity_for_score(score: int) -> Severity:
    """Traduce una puntuación 0–100 al tramo de severidad correspondiente."""
    if score >= SEVERITY_CRITICAL_FLOOR:
        return Severity.CRITICAL
    if score >= SEVERITY_HIGH_FLOOR:
        return Severity.HIGH
    if score >= SEVERITY_MEDIUM_FLOOR:
        return Severity.MEDIUM
    return Severity.LOW


class Signal(BaseModel):
    """Hallazgo concreto de un agente.

    El código es estable y sirve para agrupar o para decidir el motivo de una alerta; el
    mensaje es para leerlo.
    """

    model_config = ConfigDict(frozen=True)

    code: str = Field(description="Identificador estable del hallazgo.")
    message: str = Field(description="Descripción legible del hallazgo.")
    weight: int = Field(ge=0, le=100, description="Contribución al riesgo del agente.")


class ProjectSnapshot(BaseModel):
    """Datos del proyecto que el análisis necesita."""

    model_config = ConfigDict(frozen=True)

    id: UUID | None = Field(default=None, description="Identificador interno.")
    jira_project_key: str = Field(description="Clave del proyecto en Jira.")
    #: Sin coste por hora el impacto económico sale cero, y con él las alertas pierden su
    #: argumento más fuerte. Se registra como dato de negocio, no como detalle técnico.
    hourly_cost: float = Field(default=0.0, ge=0, description="Coste por hora del equipo.")


class CommitmentSnapshot(BaseModel):
    """Estado del compromiso en el momento del análisis."""

    model_config = ConfigDict(frozen=True)

    id: UUID | None = Field(default=None, description="Identificador interno.")
    jira_issue_key: str = Field(description="Issue de Jira que representa el compromiso.")
    title: str = Field(description="Título del compromiso.")
    due_date: datetime | None = Field(default=None, description="Fecha de vencimiento.")
    status: CommitmentStatus = Field(
        default=CommitmentStatus.OPEN, description="Estado registrado."
    )
    estimated_hours: float | None = Field(
        default=None, ge=0, description="Estimación en horas."
    )


class AgentOutcome(BaseModel):
    """Resultado de un agente.

    ``score`` es la contribución de ese agente al riesgo, no el riesgo global: componerlos es
    trabajo de ``RiskAgent``.
    """

    model_config = ConfigDict(frozen=True)

    agent: str = Field(description="Nombre del agente que produjo el resultado.")
    score: RiskScore = Field(description="Contribución al riesgo, de 0 a 100.")
    signals: list[Signal] = Field(
        default_factory=list, description="Hallazgos que justifican la puntuación."
    )
    detail: dict[str, Any] = Field(
        default_factory=dict, description="Datos adicionales del agente."
    )

    @property
    def codes(self) -> list[str]:
        """Códigos de los hallazgos, útil para decidir el motivo de una alerta."""
        return [signal.code for signal in self.signals]


class AnalysisResult(BaseModel):
    """Análisis compuesto por el orquestador."""

    model_config = ConfigDict(frozen=True)

    risk_score: RiskScore = Field(description="Riesgo global, de 0 a 100.")
    severity: Severity = Field(description="Tramo de severidad del riesgo global.")
    #: Algún agente falló y su contribución se omitió. El análisis sigue siendo utilizable,
    #: pero queda marcado como incompleto (RF-8.6).
    is_partial: bool = Field(
        default=False, description="Indica si algún agente no pudo ejecutarse."
    )
    financial_impact: float = Field(
        default=0.0, ge=0, description="Impacto económico estimado."
    )
    outcomes: list[AgentOutcome] = Field(
        default_factory=list, description="Resultado de cada agente."
    )
    primary_reason: str | None = Field(
        default=None, description="Hallazgo dominante, que da motivo a la alerta."
    )

    @property
    def signals(self) -> list[Signal]:
        """Todos los hallazgos, de todos los agentes."""
        return [signal for outcome in self.outcomes for signal in outcome.signals]

    def findings(self) -> dict[str, Any]:
        """Serializa los resultados por agente para la columna ``findings``."""
        return {
            outcome.agent: outcome.model_dump(mode="json") for outcome in self.outcomes
        }


class AnalysisRunRequest(BaseModel):
    """Cuerpo de ``POST /analysis/run``."""

    event_id: UUID | None = Field(
        default=None, description="Evento concreto a reanalizar."
    )
    project_key: str | None = Field(
        default=None,
        max_length=64,
        description="Proyecto cuyo último evento se reanaliza.",
    )


class AnalysisRead(BaseModel):
    """Análisis tal como se expone en la API."""

    id: UUID = Field(description="Identificador del análisis.")
    event_id: UUID | None = Field(default=None, description="Evento analizado.")
    commitment_id: UUID | None = Field(
        default=None, description="Compromiso analizado."
    )
    risk_score: int = Field(description="Riesgo global, de 0 a 100.")
    severity: Severity = Field(description="Tramo de severidad.")
    is_partial: bool = Field(description="Indica si el análisis quedó incompleto.")
    findings: dict[str, Any] = Field(
        default_factory=dict, description="Resultado por agente."
    )
    created_at: datetime = Field(description="Instante del análisis.")
