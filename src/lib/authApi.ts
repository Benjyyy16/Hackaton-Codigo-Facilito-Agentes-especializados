const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface CurrentUser {
  id: string
  email: string
  name: string
  roles: string[]
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try { detail = JSON.parse(text)?.detail ?? text } catch { /**/ }
    throw new Error(detail)
  }
  return res.json()
}

export async function register(email: string, name: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, name, password }),
  })
  if (!res.ok) {
    const text = await res.text()
    let detail = text
    try { detail = JSON.parse(text)?.detail ?? text } catch { /**/ }
    throw new Error(detail)
  }
  return res.json()
}

export async function getMe(token: string): Promise<CurrentUser> {
  const res = await fetch(`${BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Token inválido')
  return res.json()
}

export function getStoredToken(): string | null {
  return localStorage.getItem('datgent_token')
}

export function storeToken(token: string): void {
  localStorage.setItem('datgent_token', token)
}

export function clearToken(): void {
  localStorage.removeItem('datgent_token')
}

export function authHeaders(): Record<string, string> {
  const token = getStoredToken()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}
