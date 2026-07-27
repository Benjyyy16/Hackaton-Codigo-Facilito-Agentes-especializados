import { authHeaders } from '@/lib/authApi'
import type { LiveSession, LiveDecision, ProviderInfo } from '@/store/analysisTypes'

const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
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
  const res = await fetch(`${BASE}${path}`, {
    headers: { ...authHeaders() },
  })
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    headers: { ...authHeaders() },
  })
  if (!res.ok) throw new Error(`DELETE ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

export function startAnalysis(): Promise<{ session_id: string; state: string }> {
  return post('/live/analysis', {})
}

export function startAnalysisFromRepo(repo: {
  full_name: string
  description?: string | null
  default_branch?: string
  language?: string | null
}): Promise<{ session_id: string; state: string }> {
  return post('/live/analysis', {
    commitment: {
      title: `Análisis de ${repo.full_name}`,
      description: repo.description || `Repositorio ${repo.full_name}`,
      owner: repo.full_name.split('/')[0],
      due_date: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      priority: 'high',
    },
    signals: {
      github: {
        repo: repo.full_name,
        branch: repo.default_branch || 'main',
        language: repo.language,
      },
    },
  })
}

export function getSession(sessionId: string): Promise<LiveSession> {
  return get(`/live/analysis/${sessionId}`)
}

export function approveDecision(decisionId: string, approvedBy: string): Promise<LiveDecision> {
  return post(`/live/decisions/${decisionId}/approve`, { approved_by: approvedBy })
}

export function rejectDecision(decisionId: string, rejectedBy: string, reason: string): Promise<LiveDecision> {
  return post(`/live/decisions/${decisionId}/reject`, { rejected_by: rejectedBy, reason })
}

export function simulateJira(): Promise<{ session_id: string; state: string; message: string }> {
  return post('/live/simulate/jira')
}

export function resetSessions(): Promise<{ status: string }> {
  return del('/live/reset')
}

export function getProvenance(): Promise<{ providers: ProviderInfo[]; demo_session: boolean }> {
  return get('/live/provenance')
}
