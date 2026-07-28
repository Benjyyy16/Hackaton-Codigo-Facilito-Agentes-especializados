import { authHeaders, getStoredToken } from '@/lib/authApi'
import { requestJson } from '@/lib/http'

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

/**
 * Repos del usuario autenticado, vía el proxy del backend.
 *
 * Requiere que la instancia tenga GitHub conectado (`GITHUB_CLIENT_ID` +
 * OAuth del usuario). Si no lo está, el backend responde 404/503 y la UI
 * ofrece seguir con el caso demo en lugar de quedarse trabada.
 */
export function listUserRepos(signal?: AbortSignal): Promise<GitHubRepo[]> {
  return requestJson<GitHubRepo[]>(`${BASE}/providers/github/repos`, {
    headers: authHeaders(),
    timeoutMs: 20_000,
    signal,
  })
}

/**
 * URL para vincular la cuenta de GitHub del usuario.
 *
 * El login con GitHub sólo pide `read:user user:email`, que no alcanza para
 * listar repositorios. Esta vinculación es un paso aparte con scope `repo`; el
 * backend guarda el token y al terminar redirige de vuelta al selector.
 *
 * Es una navegación del navegador, no un fetch: el backend responde con
 * redirecciones hacia GitHub. Devuelve `null` si no hay sesión.
 */
export function connectGitHubUrl(): string | null {
  const token = getStoredToken()
  if (!token) return null
  return `${BASE}/oauth/github/authorize?token=${encodeURIComponent(token)}`
}
