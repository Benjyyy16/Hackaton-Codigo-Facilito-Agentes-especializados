import { authHeaders } from '@/lib/authApi'
import { requestJson } from '@/lib/http'

const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export interface ProjectRead {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export function listProjects(
  limit = 20,
  offset = 0,
  signal?: AbortSignal,
): Promise<ProjectRead[]> {
  return requestJson<ProjectRead[]>(`${BASE}/projects?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(),
    signal,
  })
}

export function createProject(
  name: string,
  description?: string,
  signal?: AbortSignal,
): Promise<ProjectRead> {
  return requestJson<ProjectRead>(`${BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ name, description: description ?? null }),
    signal,
  })
}
