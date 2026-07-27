import type { LiveSession, LiveDecision, ProviderInfo } from '@/store/analysisTypes'

const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try { detail = JSON.parse(text)?.detail ?? text } catch { /**/ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

/** Inicia el análisis demo (body vacío) */
export function startAnalysis(): Promise<{ session_id: string; state: string }> {
  return post('/live/analysis', {})
}

/** Obtiene el estado completo de una sesión */
export function getSession(sessionId: string): Promise<LiveSession> {
  return get(`/live/analysis/${sessionId}`)
}

/** Aprueba una decisión */
export function approveDecision(
  decisionId: string,
  approvedBy: string,
): Promise<LiveDecision> {
  return post(`/live/decisions/${decisionId}/approve`, { approved_by: approvedBy })
}

/** Rechaza una decisión */
export function rejectDecision(
  decisionId: string,
  rejectedBy: string,
  reason: string,
): Promise<LiveDecision> {
  return post(`/live/decisions/${decisionId}/reject`, {
    rejected_by: rejectedBy,
    reason,
  })
}

/** Simula evento Jira crítico (solo demo) */
export function simulateJira(): Promise<{ session_id: string; state: string; message: string }> {
  return post('/live/simulate/jira')
}

/** Limpia sesiones (solo demo) */
export function resetSessions(): Promise<{ status: string }> {
  return del('/live/reset')
}

/** Provenance: qué providers son reales */
export function getProvenance(): Promise<{ providers: ProviderInfo[]; demo_session: boolean }> {
  return get('/live/provenance')
}
