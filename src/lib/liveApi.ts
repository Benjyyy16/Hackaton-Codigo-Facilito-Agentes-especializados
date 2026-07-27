/** Cliente del ciclo de análisis en vivo. */

import type { RiskCase } from './datgentTypes'

const BASE_URL = 'https://hackaton-codigo-facilito-agentes.onrender.com'
const WAKE_UP_TIMEOUT_MS = 60_000

/** Estados del núcleo. Los valores los define el backend; la UI solo los traduce. */
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

export const CEREBRO_LABELS: Record<CerebroState, string> = {
  ready: 'listo',
  starting_agents: 'iniciando agentes',
  gathering_evidence: 'recopilando evidencia',
  consolidating: 'consolidando resultados',
  generating_scenarios: 'generando escenarios',
  awaiting_approval: 'esperando aprobación',
  completed: 'completado',
  partial_error: 'error parcial',
}

export const AGENT_STATE_LABELS: Record<LiveAgentState, string> = {
  waiting: 'esperando',
  investigating: 'investigando',
  completed: 'completado',
  error: 'error',
  insufficient_data: 'información insuficiente',
}

export interface LiveAgent {
  agent: string
  state: LiveAgentState
  duration_ms: number | null
  risk_score: number | null
  severity: string | null
  confidence: number | null
  findings_count: number
  missing_information: string[]
  error: string | null
}

export interface LiveEvidence {
  agent: string
  source_type: string
  provider: string
  external_id: string | null
  source_url: string | null
  field: string | null
  value: string | null
  explanation: string
  observed_at: string
  /** `real` si el proveedor está conectado; `demo` si el dato viene del fixture. */
  provenance: 'real' | 'demo'
}

export interface LiveDecision {
  id: string
  agent: string
  action_type: string
  title: string
  rationale: string
  payload: Record<string, unknown>
  approval_status: 'pending' | 'approved' | 'rejected'
  approved_by: string | null
  approved_at: string | null
  rejection_reason: string | null
  execution_status: string
}

export interface LiveTimelineEvent {
  at: string
  actor_type: string
  actor_name: string
  event_type: string
  summary: string
  reference: string | null
}

export interface LiveSession {
  session_id: string
  state: CerebroState
  agents: LiveAgent[]
  evidence: LiveEvidence[]
  risk_case: RiskCase | null
  decisions: LiveDecision[]
  timeline: LiveTimelineEvent[]
  agents_completed: number
  agents_total: number
  evidence_count: number
  total_duration_ms: number | null
  /** `supabase` o `memory`. La UI debe decirlo, no ocultarlo. */
  persistence: 'supabase' | 'memory'
  persistence_note: string
  started_at: string | null
  finished_at: string | null
}

export interface ProviderProvenance {
  provider: string
  connected: boolean
  provenance: 'real' | 'demo'
  label: string
}

export interface ProvenanceResponse {
  providers: ProviderProvenance[]
  demo_session: boolean
}

export class LiveApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
    this.name = 'LiveApiError'
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), WAKE_UP_TIMEOUT_MS)
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null)
      let detail = response.statusText
      if (typeof body === 'object' && body !== null) {
        const record = body as Record<string, unknown>
        if (typeof record.detail === 'string') detail = record.detail
        else if (typeof record.error === 'object' && record.error !== null) {
          const message = (record.error as Record<string, unknown>).message
          if (typeof message === 'string') detail = message
        }
      }
      throw new LiveApiError(response.status, detail)
    }
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof LiveApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new LiveApiError(0, 'El servidor no respondió en 60 segundos. Puede estar despertando.')
    }
    throw new LiveApiError(0, 'No se pudo contactar con el backend. Reintentá en unos segundos.')
  } finally {
    window.clearTimeout(timer)
  }
}

/**
 * Acuse de una aprobación o un rechazo.
 *
 * No devuelve la decisión completa a propósito: el estado íntegro vive en
 * `GET /live/analysis/{id}`, y reconstruirlo desde una respuesta parcial haría que la
 * interfaz y el servidor pudieran divergir. El acuse sirve para confirmar que la operación
 * se aceptó; el estado se relee.
 */
export interface DecisionAck {
  decision_id: string
  approved_by?: string
  approved_at?: string | null
  rejected_by?: string
  rejection_reason?: string | null
  execution_status: string
}

export const live = {
  /** Arranca el análisis. Sin cuerpo, usa el caso demo. */
  start(): Promise<{ session_id: string; state: CerebroState }> {
    return call('/live/analysis', { method: 'POST', body: JSON.stringify({}) })
  },

  session(sessionId: string): Promise<LiveSession> {
    return call(`/live/analysis/${sessionId}`)
  },

  approve(decisionId: string, approvedBy: string): Promise<DecisionAck> {
    return call(`/live/decisions/${decisionId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    })
  },

  reject(decisionId: string, rejectedBy: string, reason: string): Promise<DecisionAck> {
    return call(`/live/decisions/${decisionId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rejected_by: rejectedBy, reason }),
    })
  },

  provenance(): Promise<ProvenanceResponse> {
    return call('/live/provenance')
  },

  /** Inyecta un evento de Jira y vuelve a analizar. Solo disponible en modo demo. */
  simulateJira(): Promise<{ session_id: string }> {
    return call('/live/simulate/jira', { method: 'POST' })
  },

  reset(): Promise<{ cleared: number }> {
    return call('/live/reset', { method: 'DELETE' })
  },
}
