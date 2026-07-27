import { authHeaders } from '@/lib/authApi'
import { requestJson, type RequestOptions } from '@/lib/http'
import type { LiveSession, LiveDecision, ProviderInfo } from '@/store/analysisTypes'

const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

/**
 * Arrancar el análisis dispara los agentes LLM del backend, que en el plan
 * gratuito de Render puede además estar despertando: necesita más margen que
 * una lectura normal.
 */
const START_TIMEOUT_MS = 60_000
const READ_TIMEOUT_MS = 15_000

interface CallOptions {
  signal?: AbortSignal | null
  timeoutMs?: number
}

function jsonHeaders(): Record<string, string> {
  return { 'Content-Type': 'application/json', ...authHeaders() }
}

function call<T>(path: string, options: RequestOptions): Promise<T> {
  return requestJson<T>(`${BASE}${path}`, options)
}

export interface StartAnalysisResponse {
  session_id: string
  state: string
}

export function startAnalysis(options: CallOptions = {}): Promise<StartAnalysisResponse> {
  return call<StartAnalysisResponse>('/live/analysis', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({}),
    timeoutMs: options.timeoutMs ?? START_TIMEOUT_MS,
    signal: options.signal,
  })
}

export interface RepoLike {
  full_name: string
  description?: string | null
  default_branch?: string
  language?: string | null
}

export function startAnalysisFromRepo(
  repo: RepoLike,
  options: CallOptions = {},
): Promise<StartAnalysisResponse> {
  return call<StartAnalysisResponse>('/live/analysis', {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({
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
    }),
    timeoutMs: options.timeoutMs ?? START_TIMEOUT_MS,
    signal: options.signal,
  })
}

export function getSession(sessionId: string, options: CallOptions = {}): Promise<LiveSession> {
  return call<LiveSession>(`/live/analysis/${sessionId}`, {
    headers: authHeaders(),
    timeoutMs: options.timeoutMs ?? READ_TIMEOUT_MS,
    signal: options.signal,
  })
}

export function approveDecision(
  decisionId: string,
  approvedBy: string,
  options: CallOptions = {},
): Promise<LiveDecision> {
  return call<LiveDecision>(`/live/decisions/${decisionId}/approve`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ approved_by: approvedBy }),
    timeoutMs: options.timeoutMs ?? READ_TIMEOUT_MS,
    signal: options.signal,
  })
}

export function rejectDecision(
  decisionId: string,
  rejectedBy: string,
  reason: string,
  options: CallOptions = {},
): Promise<LiveDecision> {
  return call<LiveDecision>(`/live/decisions/${decisionId}/reject`, {
    method: 'POST',
    headers: jsonHeaders(),
    body: JSON.stringify({ rejected_by: rejectedBy, reason }),
    timeoutMs: options.timeoutMs ?? READ_TIMEOUT_MS,
    signal: options.signal,
  })
}

export function simulateJira(
  options: CallOptions = {},
): Promise<{ session_id: string; state: string; message: string }> {
  return call('/live/simulate/jira', {
    method: 'POST',
    headers: jsonHeaders(),
    timeoutMs: options.timeoutMs ?? START_TIMEOUT_MS,
    signal: options.signal,
  })
}

export function resetSessions(options: CallOptions = {}): Promise<{ status: string }> {
  return call('/live/reset', {
    method: 'DELETE',
    headers: authHeaders(),
    timeoutMs: options.timeoutMs ?? 8_000,
    signal: options.signal,
  })
}

export function getProvenance(
  options: CallOptions = {},
): Promise<{ providers: ProviderInfo[]; demo_session: boolean }> {
  return call('/live/provenance', {
    headers: authHeaders(),
    timeoutMs: options.timeoutMs ?? READ_TIMEOUT_MS,
    signal: options.signal,
  })
}
