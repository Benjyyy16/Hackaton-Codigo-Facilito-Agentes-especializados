/**
 * Tipos del contrato del backend Datgent.
 *
 * Son un espejo del contrato, no una aproximación cómoda. Dos decisiones importan:
 *
 * - Donde el backend envía un `Decimal` serializado, aquí el campo es `string`. Pasarlo a
 *   `number` al recibirlo perdería precisión en importes de dinero, que es justo el error
 *   que el backend evita usando `Decimal` en lugar de `float`.
 *
 * - Los campos que pueden llegar `null` están declarados `| null`. Un escenario sin coste
 *   estimado no es un escenario de coste cero, y la UI tiene que poder distinguirlos.
 */

export type Severity = 'low' | 'medium' | 'high' | 'critical'
export type AgentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
export type ScenarioKind = 'do_nothing' | 'add_capacity' | 'renegotiate_scope'

export interface Evidence {
  source_type: 'jira' | 'github' | 'finance' | 'supabase' | 'document' | 'computed'
  provider: string
  external_id: string | null
  source_url: string | null
  field: string | null
  value: string | null
  content: string | null
  observed_at: string
  explanation: string
}

export interface Finding {
  category: string
  code: string
  severity: Severity
  risk_score: number
  confidence: number
  summary: string
  impact: string | null
  evidence: Evidence[]
}

export interface RecommendedAction {
  action_type: string
  title: string
  rationale: string
  payload: Record<string, unknown>
  requires_human_approval: boolean
  estimated_effort_hours: number | null
}

export interface AgentOutput {
  agent: string
  status: AgentStatus
  risk_score: number
  severity: Severity
  confidence: number
  summary: string
  findings: Finding[]
  evidence: Evidence[]
  missing_information: string[]
  recommended_actions: RecommendedAction[]
  requires_human_approval: boolean
}

export interface CausalStep {
  step: number
  cause: string
  effect: string
  confidence: number
  evidence_refs: string[]
}

export interface PreMortem {
  assumed_failure: string
  failure_modes: string[]
  early_signals: string[]
  preventive_actions: string[]
}

export interface Scenario {
  kind: ScenarioKind
  title: string
  description: string
  expected_delay_days: number | null
  /** Importe serializado. Se conserva como texto para no perder precisión. */
  expected_cost: string | null
  residual_exposure: string | null
  completion_probability: number | null
  client_risk: string | null
  technical_impact: string | null
  new_scope: string | null
  new_due_date: string | null
  affected_commitments: string[]
}

export interface RiskCase {
  consolidated_score: number
  severity: Severity
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
  agent_outputs: AgentOutput[]
}

export interface ProposedAction {
  agent: string
  action_type: string
  title: string
  rationale: string
  requires_human_approval: boolean
  payload: Record<string, unknown>
}

export interface OrchestrateResponse {
  /** Siempre `false`: el análisis no se guardó en ningún sitio. */
  persisted: boolean
  risk_case: RiskCase
  agent_outputs: AgentOutput[]
  proposed_actions: ProposedAction[]
  analyzed_at: string
}

export interface DependencyHealth {
  name: string
  status: 'up' | 'down' | 'unknown'
  latency_ms: number | null
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  service: string
  version: string
  environment: string
  dependencies: DependencyHealth[]
}

export interface SchemaStatus {
  ready: boolean
  tables: Array<{ name: string; exists: boolean }>
  missing: string[]
  can_apply_automatically: boolean
  hint: string
}

export interface WsEvent {
  type: string
  version: string
  occurred_at: string
  project_id: string | null
  commitment_id: string | null
  risk_case_id: string | null
  data: Record<string, unknown>
}

// ── Flujo vivo ────────────────────────────────────────────────────────────────

export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

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
  execution_status: string
  created_at: string
}

export interface LiveAgentRecord {
  agent: string
  state: string
  duration_ms: number
  risk_score: number
  severity: string
  confidence: number
  findings_count: number
  missing_information: string[]
}

export interface LiveSession {
  session_id: string
  state: string
  agents: LiveAgentRecord[]
  evidence: unknown[]
  risk_case: {
    consolidated_score: number
    severity: string
    confidence: number
    summary: string
    causal_chain: string[]
    premortem: string
    scenarios: { label: string; description: string; probability: number; impact: number }[]
    facts: string[]
    inferences: string[]
    assumptions: string[]
    missing_information: string[]
    is_partial: boolean
  } | null
  decisions: LiveDecision[]
  timeline: unknown[]
  agents_completed: number
  agents_total: number
  evidence_count: number
  total_duration_ms: number
  started_at: string | null
  finished_at: string | null
}
