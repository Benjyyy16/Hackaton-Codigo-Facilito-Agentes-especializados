"""Modelo de dominio de Datgent.

La entidad central es ``Commitment``. Todo lo demas cuelga de ella: los eventos que
la afectan, los agentes que la analizan, los hallazgos que producen, la evidencia que
los respalda, el riesgo consolidado, la alerta y las decisiones que requieren
aprobacion.

Que la entidad sea una y no cuatro es lo que hace que Datgent no sea "cuatro
dashboards": el agente financiero y el de codigo hablan del mismo compromiso, y por
eso sus hallazgos se pueden correlacionar.

Los enums son cerrados y coinciden con las restricciones ``check`` de ``db/schema.sql``.
Si divergen, la base de datos rechaza la escritura, que es el fallo deseado: mejor un
error de insercion que una fila con un estado que nadie sabe interpretar.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StrEnum

# ---------------------------------------------------------------------------------
# Tipos compartidos
# ---------------------------------------------------------------------------------

#: Puntuacion de riesgo. La escala es 0-100 en todo el sistema, sin excepciones.
RiskScore = Annotated[int, Field(ge=0, le=100)]

#: Confianza del agente en su propio hallazgo. Un dato duro va cerca de 1.0; una
#: inferencia del LLM, mas abajo. Sin esto, un hallazgo especulativo pesa igual que
#: uno verificado.
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

#: Importe monetario. ``Decimal`` y no ``float``: el dinero no se representa en binario.
Money = Annotated[Decimal, Field(ge=0, decimal_places=2)]


class Severity(StrEnum):
    """Gravedad de un hallazgo, un caso de riesgo o una alerta."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


#: Umbrales de severidad. La severidad describe la gravedad; el umbral de alerta
#: (configurable) decide si se avisa. Son cosas distintas a proposito.
SEVERITY_MEDIUM_FLOOR = 40
SEVERITY_HIGH_FLOOR = 60
SEVERITY_CRITICAL_FLOOR = 80


def severity_for_score(score: int) -> Severity:
    """Traduce una puntuacion 0-100 al tramo de severidad correspondiente."""
    if score >= SEVERITY_CRITICAL_FLOOR:
        return Severity.CRITICAL
    if score >= SEVERITY_HIGH_FLOOR:
        return Severity.HIGH
    if score >= SEVERITY_MEDIUM_FLOOR:
        return Severity.MEDIUM
    return Severity.LOW


class Priority(StrEnum):
    """Prioridad declarada de un compromiso."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------------
# projects
# ---------------------------------------------------------------------------------


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ProjectCreate(BaseModel):
    """Cuerpo de ``POST /projects``."""

    name: str = Field(min_length=1, max_length=200, description="Nombre del proyecto.")
    description: str | None = Field(default=None, max_length=2000)
    status: ProjectStatus = Field(default=ProjectStatus.ACTIVE)
    #: Referencias en sistemas externos: ``{"jira": "DAT", "github": "owner/repo"}``.
    #: Es un mapa y no columnas fijas porque anadir un provider no debe ser una migracion.
    external_references: dict[str, str] = Field(default_factory=dict)
    hourly_cost: Money = Field(default=Decimal("0"), description="Coste por hora del equipo.")
    currency: str = Field(default="USD", min_length=3, max_length=3)


class ProjectRead(BaseModel):
    """Proyecto tal como se expone en la API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    status: ProjectStatus
    external_references: dict[str, Any] = Field(default_factory=dict)
    hourly_cost: Decimal = Decimal("0")
    currency: str = "USD"
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------------
# commitments  -- la entidad central
# ---------------------------------------------------------------------------------


class CommitmentStatus(StrEnum):
    """Ciclo de vida de un compromiso.

    ``open`` -> ``at_risk`` -> (``breached`` | ``met``), con ``cancelled`` como salida
    lateral. ``at_risk`` lo fija el orquestador cuando el riesgo consolidado cruza el
    umbral; no es un estado que se declare a mano.
    """

    OPEN = "open"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    MET = "met"
    CANCELLED = "cancelled"


class CommitmentSource(StrEnum):
    """De donde nacio el compromiso."""

    MANUAL = "manual"
    CONTRACT = "contract"
    JIRA = "jira"
    GITHUB = "github"
    IMPORT = "import"
    DEMO = "demo"


class CommitmentCreate(BaseModel):
    """Cuerpo de ``POST /commitments``."""

    project_id: UUID
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    beneficiary: str | None = Field(default=None, max_length=200, description="Quien lo recibe.")
    owner: str | None = Field(default=None, max_length=200, description="Quien responde por el.")
    due_date: datetime | None = None
    #: Dinero expuesto si se incumple. Es el numero que convierte un retraso tecnico en
    #: una conversacion de negocio.
    financial_exposure: Money = Field(default=Decimal("0"))
    currency: str = Field(default="USD", min_length=3, max_length=3)
    priority: Priority = Field(default=Priority.MEDIUM)
    source: CommitmentSource = Field(default=CommitmentSource.MANUAL)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommitmentUpdate(BaseModel):
    """Cuerpo de ``PATCH /commitments/{id}``. Todos los campos son opcionales."""

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    beneficiary: str | None = Field(default=None, max_length=200)
    owner: str | None = Field(default=None, max_length=200)
    due_date: datetime | None = None
    financial_exposure: Money | None = None
    priority: Priority | None = None
    status: CommitmentStatus | None = None
    metadata: dict[str, Any] | None = None


class CommitmentRead(BaseModel):
    """Compromiso tal como se expone en la API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    description: str | None = None
    beneficiary: str | None = None
    owner: str | None = None
    due_date: datetime | None = None
    financial_exposure: Decimal = Decimal("0")
    currency: str = "USD"
    priority: Priority = Priority.MEDIUM
    status: CommitmentStatus = CommitmentStatus.OPEN
    source: CommitmentSource = CommitmentSource.MANUAL
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CommitmentSnapshot(BaseModel):
    """Vista de solo lectura que reciben los agentes.

    Es un modelo aparte de ``CommitmentRead`` a proposito: los agentes no deben poder
    mutar el compromiso ni depender de campos de presentacion. Congelado para que un
    agente no pueda alterar el contexto que otro va a leer.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    project_id: UUID | None = None
    title: str
    description: str | None = None
    beneficiary: str | None = None
    owner: str | None = None
    due_date: datetime | None = None
    financial_exposure: Decimal = Decimal("0")
    currency: str = "USD"
    priority: Priority = Priority.MEDIUM
    status: CommitmentStatus = CommitmentStatus.OPEN
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectSnapshot(BaseModel):
    """Vista de solo lectura del proyecto para los agentes."""

    model_config = ConfigDict(frozen=True)

    id: UUID | None = None
    name: str
    hourly_cost: Decimal = Decimal("0")
    currency: str = "USD"
    external_references: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------------
# provider_connections
# ---------------------------------------------------------------------------------


class ConnectionStatus(StrEnum):
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class ProviderConnectionRead(BaseModel):
    """Estado de la conexion a un sistema externo.

    ``config`` nunca contiene secretos: solo parametros no sensibles y referencias al
    nombre de la variable de entorno que los guarda.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None = None
    provider: str
    status: ConnectionStatus = ConnectionStatus.UNKNOWN
    config: dict[str, Any] = Field(default_factory=dict)
    last_sync_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------------
# source_events
# ---------------------------------------------------------------------------------


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceEventCreate(BaseModel):
    """Evento normalizado, listo para persistir."""

    provider: str
    external_id: str
    event_type: str
    #: ``sha256(provider:external_id:event_type:occurred_at)``. La unicidad la garantiza
    #: la base de datos, no la aplicacion: es lo que cierra la carrera entre dos entregas
    #: simultaneas del mismo webhook.
    event_hash: str
    project_id: UUID | None = None
    commitment_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class SourceEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    external_id: str
    event_type: str
    event_hash: str
    project_id: UUID | None = None
    commitment_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
    received_at: datetime
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    processing_error: str | None = None


# ---------------------------------------------------------------------------------
# agent_runs, findings, evidence
# ---------------------------------------------------------------------------------


class AgentRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class EvidenceSourceType(StrEnum):
    """Origen de una evidencia.

    ``computed`` es para lo que el sistema deriva de otros datos (por ejemplo, "quedan
    12 horas de margen"). Marcarlo distinto de un dato observado importa: una evidencia
    calculada hereda la incertidumbre de sus entradas.
    """

    JIRA = "jira"
    GITHUB = "github"
    FINANCE = "finance"
    SUPABASE = "supabase"
    DOCUMENT = "document"
    COMPUTED = "computed"


class Evidence(BaseModel):
    """Dato observable que respalda un hallazgo.

    Sin evidencia un hallazgo es una opinion. El contrato obliga a decir de donde sale
    cada afirmacion, y por eso ``source_type`` y ``explanation`` no son opcionales.
    """

    model_config = ConfigDict(frozen=True)

    source_type: EvidenceSourceType
    provider: str = Field(description="Nombre del proveedor concreto.")
    external_id: str | None = Field(default=None, description="Identificador en el origen.")
    source_url: str | None = Field(default=None, description="Enlace al elemento.")
    field: str | None = Field(default=None, description="Campo observado.")
    value: str | None = Field(default=None, description="Valor observado, como texto.")
    content: str | None = Field(default=None, description="Fragmento relevante.")
    observed_at: datetime
    explanation: str = Field(description="Por que este dato es relevante.")
    metadata: dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    """Hallazgo concreto de un agente.

    ``code`` es estable y sirve para agrupar o decidir el motivo de una alerta;
    ``summary`` es para leerlo. ``evidence`` no tiene default vacio por descuido: un
    hallazgo sin evidencia se puede crear, pero el orquestador lo pondera menos.
    """

    model_config = ConfigDict(frozen=True)

    category: str = Field(description="Familia: schedule, technical, financial, data, security.")
    code: str = Field(description="Identificador estable del hallazgo.")
    severity: Severity
    risk_score: RiskScore
    confidence: Confidence = 1.0
    summary: str
    impact: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    """Accion que el agente propone.

    ``requires_human_approval`` no es decorativo: si es ``True``, el orquestador crea
    una ``Decision`` y no ejecuta nada.
    """

    model_config = ConfigDict(frozen=True)

    action_type: str
    title: str
    rationale: str
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_human_approval: bool = True
    estimated_effort_hours: float | None = Field(default=None, ge=0)


class AgentOutput(BaseModel):
    """Salida estructurada de un agente especializado.

    Es el contrato que hace comparables a agentes distintos. ``missing_information`` es
    obligatorio en espiritu: un agente que no puede concluir debe decir que le falta en
    lugar de rellenar el hueco con una suposicion presentada como hallazgo.
    """

    model_config = ConfigDict(frozen=True)

    agent: str
    commitment_id: UUID | None = None
    status: AgentRunStatus = AgentRunStatus.COMPLETED
    risk_score: RiskScore = 0
    severity: Severity = Severity.LOW
    confidence: Confidence = 1.0
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    requires_human_approval: bool = False
    error: str | None = None

    @property
    def all_evidence(self) -> list[Evidence]:
        """Evidencia propia mas la de cada hallazgo, sin duplicar la referencia."""
        collected = list(self.evidence)
        for finding in self.findings:
            collected.extend(finding.evidence)
        return collected


class AgentRunRead(BaseModel):
    """Ejecucion de un agente tal como se expone en ``GET /agent-runs/{id}``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_name: str
    commitment_id: UUID | None = None
    status: AgentRunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    model: str | None = None
    prompt_version: str | None = None
    input_reference: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int | None = None
    created_at: datetime


# ---------------------------------------------------------------------------------
# risk_cases: cadena causal, pre-mortem, escenarios
# ---------------------------------------------------------------------------------


class CausalStep(BaseModel):
    """Un eslabon de la cadena causal.

    La cadena es lo que convierte cuatro listas de hallazgos en una explicacion: no
    "hay un PR bloqueado y falta presupuesto", sino "el PR bloqueado retrasa la entrega,
    el retraso dispara la penalizacion".
    """

    model_config = ConfigDict(frozen=True)

    step: int = Field(ge=1)
    cause: str
    effect: str
    confidence: Confidence = 1.0
    evidence_refs: list[str] = Field(default_factory=list)


class PreMortem(BaseModel):
    """Analisis pre-mortem: asumir el fallo y trabajar hacia atras.

    Se pide asi, y no como "lista de riesgos", porque partir del fallo consumado
    produce modos de fallo concretos en lugar de preocupaciones genericas.
    """

    model_config = ConfigDict(frozen=True)

    assumed_failure: str = Field(description="El compromiso se incumplio. Que paso.")
    failure_modes: list[str] = Field(default_factory=list)
    early_signals: list[str] = Field(default_factory=list, description="Que se veria antes.")
    preventive_actions: list[str] = Field(default_factory=list)


class ScenarioKind(StrEnum):
    """Los tres escenarios obligatorios."""

    DO_NOTHING = "do_nothing"
    ADD_CAPACITY = "add_capacity"
    RENEGOTIATE_SCOPE = "renegotiate_scope"


class Scenario(BaseModel):
    """Escenario de recuperacion con su coste y su riesgo residual.

    Los tres se presentan siempre, incluido "no actuar": sin la linea base de la
    inaccion, el coste de las otras dos opciones no se puede juzgar.
    """

    model_config = ConfigDict(frozen=True)

    kind: ScenarioKind
    title: str
    description: str
    expected_delay_days: float | None = Field(default=None, ge=0)
    expected_cost: Decimal | None = Field(default=None, ge=0)
    residual_exposure: Decimal | None = Field(default=None, ge=0)
    completion_probability: float | None = Field(default=None, ge=0, le=1)
    client_risk: str | None = None
    technical_impact: str | None = None
    affected_commitments: list[str] = Field(default_factory=list)
    new_scope: str | None = None
    new_due_date: datetime | None = None


class RiskCaseStatus(StrEnum):
    OPEN = "open"
    MONITORING = "monitoring"
    MITIGATED = "mitigated"
    CLOSED = "closed"


class RiskCase(BaseModel):
    """Riesgo consolidado de un compromiso: la salida del orquestador.

    La separacion entre ``facts``, ``inferences`` y ``assumptions`` es deliberada y no
    cosmetica: un plan que no distingue lo observado de lo supuesto no se puede
    auditar, y quien decide no sabe cuanto peso darle.
    """

    model_config = ConfigDict(frozen=True)

    commitment_id: UUID | None = None
    consolidated_score: RiskScore
    severity: Severity
    confidence: Confidence = 1.0
    summary: str = ""
    causal_chain: list[CausalStep] = Field(default_factory=list)
    premortem: PreMortem | None = None
    scenarios: list[Scenario] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    #: Algun agente fallo y su contribucion se omitio. El caso sigue siendo utilizable,
    #: pero queda marcado.
    is_partial: bool = False
    agent_outputs: list[AgentOutput] = Field(default_factory=list)


class RiskCaseRead(BaseModel):
    """Caso de riesgo tal como se expone en la API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    commitment_id: UUID
    consolidated_score: int
    severity: Severity
    confidence: float
    causal_chain: list[dict[str, Any]] = Field(default_factory=list)
    premortem: dict[str, Any] = Field(default_factory=dict)
    scenarios: list[dict[str, Any]] = Field(default_factory=list)
    facts: list[Any] = Field(default_factory=list)
    inferences: list[Any] = Field(default_factory=list)
    assumptions: list[Any] = Field(default_factory=list)
    missing_information: list[Any] = Field(default_factory=list)
    summary: str | None = None
    is_partial: bool = False
    status: RiskCaseStatus = RiskCaseStatus.OPEN
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------------
# alerts
# ---------------------------------------------------------------------------------


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    risk_case_id: UUID | None = None
    commitment_id: UUID | None = None
    severity: Severity
    title: str
    description: str | None = None
    status: AlertStatus = AlertStatus.OPEN
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime


class AlertAcknowledge(BaseModel):
    """Cuerpo de ``PATCH /alerts/{id}/acknowledge``."""

    acknowledged_by: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------------
# decisions: aprobacion humana
# ---------------------------------------------------------------------------------


class ActionType(StrEnum):
    """Acciones que el sistema puede proponer.

    Todas requieren aprobacion humana. El enum es cerrado porque cada valor tiene un
    ejecutor asociado: admitir cadenas libres significaria aceptar propuestas que nadie
    sabe ejecutar.
    """

    POST_ACCOUNTING_ENTRY = "post_accounting_entry"
    UPDATE_JIRA_ISSUE = "update_jira_issue"
    CLOSE_CRITICAL_ALERT = "close_critical_alert"
    EXECUTE_SQL = "execute_sql"
    BLOCK_DEPLOYMENT = "block_deployment"
    CREATE_PULL_REQUEST = "create_pull_request"
    MERGE_PULL_REQUEST = "merge_pull_request"
    SEND_EXTERNAL_COMMUNICATION = "send_external_communication"
    REASSIGN_OWNER = "reassign_owner"
    RENEGOTIATE_SCOPE = "renegotiate_scope"
    ADD_CAPACITY = "add_capacity"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExecutionStatus(StrEnum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    risk_case_id: UUID | None = None
    commitment_id: UUID | None = None
    action_type: ActionType
    title: str
    rationale: str | None = None
    proposed_payload: dict[str, Any] = Field(default_factory=dict)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = "orchestrator-agent"
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    execution_status: ExecutionStatus = ExecutionStatus.NOT_STARTED
    execution_result: dict[str, Any] = Field(default_factory=dict)
    executed_at: datetime | None = None
    error: str | None = None
    created_at: datetime


class DecisionApprove(BaseModel):
    """Cuerpo de ``POST /decisions/{id}/approve``."""

    approved_by: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


class DecisionReject(BaseModel):
    """Cuerpo de ``POST /decisions/{id}/reject``."""

    rejected_by: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)


# ---------------------------------------------------------------------------------
# timeline_events
# ---------------------------------------------------------------------------------


class ActorType(StrEnum):
    SYSTEM = "system"
    AGENT = "agent"
    HUMAN = "human"
    PROVIDER = "provider"


class TimelineEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    commitment_id: UUID
    actor_type: ActorType
    actor_name: str
    event_type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ---------------------------------------------------------------------------------
# documents (RAG)
# ---------------------------------------------------------------------------------


class DocumentCreate(BaseModel):
    """Fragmento de texto asociado a un proyecto o compromiso."""

    project_id: UUID | None = None
    commitment_id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=50_000)
    source_type: str = "document"
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None = None
    commitment_id: UUID | None = None
    title: str
    content: str
    source_type: str = "document"
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RetrievedChunk(BaseModel):
    """Fragmento recuperado por el RAG, con su puntuacion de relevancia."""

    model_config = ConfigDict(frozen=True)

    document_id: UUID | None = None
    title: str
    content: str
    score: float = Field(ge=0)
    #: ``vector`` si se uso pgvector, ``fulltext`` si fue busqueda textual. Importa
    #: saberlo: la calidad de la recuperacion no es la misma.
    strategy: str = "fulltext"
    source_url: str | None = None
