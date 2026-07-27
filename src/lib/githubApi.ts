import { authHeaders } from './authApi'

const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export interface GitHubRepo {
  id: number
  name: string
  full_name: string
  description: string | null
  html_url: string
  private: boolean
  default_branch: string
  language: string | null
  stargazers_count: number
  updated_at: string
}

export async function listUserRepos(): Promise<GitHubRepo[]> {
  const res = await fetch(`${BASE}/providers/github/repos`, {
    headers: { ...authHeaders() },
  })
  if (!res.ok) throw new Error(`GET /providers/github/repos → ${res.status}`)
  return res.json()
}
