import { authHeaders } from '@/lib/authApi'

const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export interface ProjectRead {
  id: string
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export async function listProjects(limit = 20, offset = 0): Promise<ProjectRead[]> {
  const res = await fetch(`${BASE}/projects?limit=${limit}&offset=${offset}`, {
    headers: { ...authHeaders() },
  })
  if (!res.ok) throw new Error(`GET /projects → ${res.status}`)
  return res.json()
}

export async function createProject(name: string, description?: string): Promise<ProjectRead> {
  const res = await fetch(`${BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ name, description: description ?? null }),
  })
  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try { detail = JSON.parse(text)?.detail ?? text } catch { /**/ }
    throw new Error(detail)
  }
  return res.json()
}
