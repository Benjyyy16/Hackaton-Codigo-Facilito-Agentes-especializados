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

export interface Scenario {
  label: string
  description: string
  probability: number
  impact: number
}

export interface RiskCase {
  commitment_id: string
  consolidated_score: number
  severity: string
  confidence: number
  summary: string
  causal_chain: string[]
  premortem: string
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

// Eventos WebSocket
export type WsEventType =
  | 'source_event.received'
  | 'analysis.started'
  | 'agent_run.started'
  | 'agent_run.completed'
  | 'risk_case.created'
  | 'risk_case.updated'
  | 'alert.created'
  | 'evidence.created'
  | 'decision.created'
  | 'decision.approved'
  | 'decision.rejected'
  | 'decision.updated'
  | 'timeline.appended'
  | 'analysis.completed'
  | 'pong'

export interface WsEvent {
  type: WsEventType
  version?: string
  occurred_at?: string
  data: Record<string, unknown>
}

// Estado del store de análisis
export type WsConnectionState = 'live' | 'reconnecting' | 'disconnected'

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
