// Tipos del flujo vivo de Datgent — espejo del backend

export type CerebroState =
  | 'ready'
  | 'starting_agents'
  | 'gathering_evidence'
  | 'consolidating'
  | 'generating_scenarios'
  | 'awaiting_approval'
  | 'completed'
  | 'partial_error'

export type LiveAgentState =
  | 'waiting'
  | 'investigating'
  | 'completed'
  | 'error'
  | 'insufficient_data'

export interface LiveAgentRecord {
  agent: string
  state: LiveAgentState
  duration_ms: number
  risk_score: number
  severity: string
  confidence: number
  findings_count: number
  missing_information: string[]
}

export interface Evidence {
  agent: string
  source_type: string
  provider: string
  external_id: string | null
  field: string
  value: string
  explanation: string
  observed_at: string
  provenance: 'real' | 'demo'
}

export interface Finding {
  code: string
  summary: string
  risk_score: number
  severity: string
}

/**
 * Escenario de recuperación. El backend manda más campos de los que la UI
 * muestra; se tipan los opcionales para no volver a asumir de menos.
 */
export interface Scenario {
  kind?: string
  title?: string
  description?: string
  expected_delay_days?: number | null
  expected_cost?: number | string | null
  residual_exposure?: number | string | null
  completion_probability?: number | null
  client_risk?: string | null
  technical_impact?: string | null
  /** Campos del formato viejo, por si alguna respuesta los trae. */
  label?: string
  probability?: number
  impact?: number
}

/** Un eslabón de la cadena causal. El backend lo manda como objeto. */
export interface CausalStep {
  step?: number
  cause: string
  effect: string
  confidence?: number
  evidence_refs?: string[]
}

/**
 * Pre-mortem: el backend lo devuelve como objeto, no como texto. Renderizarlo
 * directo como hijo de React tira el error #31.
 */
export interface PreMortem {
  assumed_failure: string
  failure_modes: string[]
  early_signals: string[]
  preventive_actions: string[]
}

export interface RiskCase {
  commitment_id: string
  consolidated_score: number
  severity: string
  confidence: number
  summary: string
  causal_chain: CausalStep[]
  premortem: PreMortem | null
  scenarios: Scenario[]
  facts: string[]
  inferences: string[]
  assumptions: string[]
  missing_information: string[]
  is_partial: boolean
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected'
export type ExecutionStatus = 'not_started' | 'running' | 'completed' | 'failed'

export interface LiveDecision {
  id: string
  action_type: string
  title: string
  rationale: string
  payload: Record<string, unknown>
  agent: string
  approval_status: ApprovalStatus
  approved_by: string | null
  approved_at: string | null
  rejection_reason: string | null
  execution_status: ExecutionStatus
  created_at: string
}

export interface TimelineEntry {
  id: string
  actor_type: string
  actor_name: string
  event_type: string
  summary: string
  at: string
}

export interface LiveSession {
  session_id: string
  state: CerebroState
  agents: LiveAgentRecord[]
  evidence: Evidence[]
  risk_case: RiskCase | null
  decisions: LiveDecision[]
  timeline: TimelineEntry[]
  agents_completed: number
  agents_total: number
  evidence_count: number
  total_duration_ms: number
  persistence: string
  started_at: string | null
  finished_at: string | null
}

// Alert
export interface Alert {
  id: string
  severity: string
  title: string
  message: string
  source_agent: string
  status: 'active' | 'acknowledged' | 'resolved'
  created_at: string
  acknowledged_at?: string | null
  resolved_at?: string | null
}

// Commitment
export interface Commitment {
  id: string
  title: string
  status: string
  previous_status?: string
}

// ── Eventos WebSocket ─────────────────────────────────────────────
// Unión discriminada: el `switch (event.type)` del reducer estrecha `data`
// al payload correcto, así no hacen falta casts sueltos en cada rama.

export type WsEventType =
  | 'source_event.received'
  | 'analysis.started'
  | 'agent_run.started'
  | 'agent_run.completed'
  | 'evidence.created'
  | 'risk_case.created'
  | 'risk_case.updated'
  | 'alert.created'
  | 'alert.acknowledged'
  | 'alert.resolved'
  | 'decision.created'
  | 'decision.approved'
  | 'decision.rejected'
  | 'decision.updated'
  | 'decision.executed'
  | 'commitment.status_changed'
  | 'timeline.appended'
  | 'analysis.completed'
  | 'cerebro.state_changed'
  | 'pong'

interface WsEnvelope {
  version?: string
  occurred_at?: string
}

export interface AgentStartedPayload {
  agent: string
}

export interface AgentCompletedPayload {
  agent: string
  status?: LiveAgentState
  risk_score?: number
  severity?: string
  confidence?: number
  findings?: Finding[]
  duration_ms?: number
  missing_information?: string[]
}

export interface AnalysisStartedPayload {
  session_id?: string
}

export interface RiskUpdatedPayload {
  consolidated_score: number
  severity: string
  confidence: number
}

export interface DecisionExecutedPayload {
  id: string
  execution_status: ExecutionStatus
}

export interface AnalysisCompletedPayload {
  state: CerebroState
  consolidated_score?: number
}

export interface CerebroStateChangedPayload {
  state: CerebroState
}

export interface AlertRefPayload {
  id: string
}

export type WsEvent = WsEnvelope &
  (
    | { type: 'source_event.received'; data: Record<string, unknown> }
    | { type: 'analysis.started'; data: AnalysisStartedPayload }
    | { type: 'agent_run.started'; data: AgentStartedPayload }
    | { type: 'agent_run.completed'; data: AgentCompletedPayload }
    | { type: 'evidence.created'; data: Evidence }
    | { type: 'risk_case.created'; data: RiskCase }
    | { type: 'risk_case.updated'; data: RiskUpdatedPayload }
    | { type: 'alert.created'; data: Alert }
    | { type: 'alert.acknowledged'; data: AlertRefPayload }
    | { type: 'alert.resolved'; data: AlertRefPayload }
    | { type: 'decision.created'; data: LiveDecision }
    | { type: 'decision.updated'; data: LiveDecision }
    | { type: 'decision.approved'; data: LiveDecision }
    | { type: 'decision.rejected'; data: LiveDecision }
    | { type: 'decision.executed'; data: DecisionExecutedPayload }
    | { type: 'commitment.status_changed'; data: Commitment }
    | { type: 'timeline.appended'; data: TimelineEntry }
    | { type: 'analysis.completed'; data: AnalysisCompletedPayload }
    | { type: 'cerebro.state_changed'; data: CerebroStateChangedPayload }
    | { type: 'pong'; data: Record<string, unknown> }
  )

const WS_EVENT_TYPES: readonly WsEventType[] = [
  'source_event.received',
  'analysis.started',
  'agent_run.started',
  'agent_run.completed',
  'evidence.created',
  'risk_case.created',
  'risk_case.updated',
  'alert.created',
  'alert.acknowledged',
  'alert.resolved',
  'decision.created',
  'decision.approved',
  'decision.rejected',
  'decision.updated',
  'decision.executed',
  'commitment.status_changed',
  'timeline.appended',
  'analysis.completed',
  'cerebro.state_changed',
  'pong',
]

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/**
 * Valida un mensaje crudo del socket. Devuelve `null` si no es un evento
 * reconocible, para descartarlo sin romper el reducer.
 */
export function parseWsEvent(raw: unknown): WsEvent | null {
  if (!isRecord(raw)) return null
  const type = raw.type
  if (typeof type !== 'string') return null
  if (!WS_EVENT_TYPES.includes(type as WsEventType)) return null

  const data = isRecord(raw.data) ? raw.data : {}

  // Los eventos cuyo payload el reducer indexa por clave necesitan esa clave
  switch (type as WsEventType) {
    case 'agent_run.started':
    case 'agent_run.completed':
      if (typeof data.agent !== 'string') return null
      break
    case 'alert.acknowledged':
    case 'alert.resolved':
    case 'decision.executed':
      if (typeof data.id !== 'string') return null
      break
    case 'decision.created':
    case 'decision.updated':
    case 'decision.approved':
    case 'decision.rejected':
      if (typeof data.id !== 'string') return null
      break
    case 'commitment.status_changed':
      if (typeof data.id !== 'string') return null
      break
    default:
      break
  }

  return {
    type,
    version: typeof raw.version === 'string' ? raw.version : undefined,
    occurred_at: typeof raw.occurred_at === 'string' ? raw.occurred_at : undefined,
    data,
  } as WsEvent
}

// Estado del store de análisis
export type WsConnectionState =
  | 'live'
  | 'reconnecting'
  | 'disconnected'
  /** Se agotaron los reintentos y el polling: el backend no responde. */
  | 'offline'

export interface AnalysisStore {
  session: LiveSession | null
  sessionId: string | null
  wsState: WsConnectionState
  isRunning: boolean
  error: string | null
}

// Provenance
export interface ProviderInfo {
  provider: string
  connected: boolean
  provenance: 'real' | 'demo'
  label: string
}
