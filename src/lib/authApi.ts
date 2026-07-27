import { requestJson } from '@/lib/http'
import { readJson, readItem, removeItem, writeJson } from '@/lib/storage'

const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

/** Clave actual. `datgent_token` es el formato viejo (sólo el string del JWT). */
const SESSION_KEY = 'datgent.auth.v1'
const LEGACY_TOKEN_KEY = 'datgent_token'

/** Margen para considerar el token vencido antes de que realmente expire. */
const EXPIRY_SKEW_MS = 30_000

export interface TokenResponse {
  access_token: string
  refresh_token?: string
  token_type: string
  expires_in: number
}

export interface CurrentUser {
  id: string
  email: string
  name: string
  roles: string[]
}

interface StoredSession {
  access_token: string
  refresh_token: string | null
  /** Epoch ms. `null` si el backend no informó `expires_in`. */
  expires_at: number | null
}

// ── Aviso de sesión expirada ────────────────────────────────────────
// El store se suscribe para hacer logout automático sin importar quién
// detecte primero el vencimiento (una request o el temporizador).

type ExpiryListener = () => void
const expiryListeners = new Set<ExpiryListener>()

export function onSessionExpired(listener: ExpiryListener): () => void {
  expiryListeners.add(listener)
  return () => expiryListeners.delete(listener)
}

let notifying = false
function notifyExpired() {
  if (notifying) return
  notifying = true
  try {
    for (const listener of expiryListeners) listener()
  } finally {
    notifying = false
  }
}

// ── Persistencia ────────────────────────────────────────────────────

function readSession(): StoredSession | null {
  const current = readJson<StoredSession>(SESSION_KEY)
  if (current?.access_token) return current

  // Migración desde el formato viejo: sin expiración conocida
  const legacy = readItem(LEGACY_TOKEN_KEY)
  if (legacy) {
    const migrated: StoredSession = {
      access_token: legacy,
      refresh_token: null,
      expires_at: expiryFromJwt(legacy),
    }
    writeJson(SESSION_KEY, migrated)
    removeItem(LEGACY_TOKEN_KEY)
    return migrated
  }
  return null
}

/** Lee `exp` del payload del JWT (epoch ms) para tokens sin `expires_in`. */
function expiryFromJwt(token: string): number | null {
  try {
    const payload = token.split('.')[1]
    if (!payload) return null
    const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'))
    const parsed: unknown = JSON.parse(json)
    if (parsed && typeof parsed === 'object' && 'exp' in parsed) {
      const exp = (parsed as { exp: unknown }).exp
      if (typeof exp === 'number') return exp * 1000
    }
  } catch {
    /* token opaco o no-JWT */
  }
  return null
}

export function storeToken(token: string, expiresInSeconds?: number, refreshToken?: string): void {
  const expiresAt =
    typeof expiresInSeconds === 'number' && expiresInSeconds > 0
      ? Date.now() + expiresInSeconds * 1000
      : expiryFromJwt(token)

  writeJson(SESSION_KEY, {
    access_token: token,
    refresh_token: refreshToken ?? null,
    expires_at: expiresAt,
  } satisfies StoredSession)
}

export function storeSession(tokens: TokenResponse): void {
  storeToken(tokens.access_token, tokens.expires_in, tokens.refresh_token)
}

export function clearToken(): void {
  removeItem(SESSION_KEY)
  removeItem(LEGACY_TOKEN_KEY)
}

/** `true` si hay token guardado y ya venció (con margen de seguridad). */
export function isTokenExpired(): boolean {
  const session = readSession()
  if (!session) return false
  if (session.expires_at === null) return false
  return Date.now() >= session.expires_at - EXPIRY_SKEW_MS
}

/** Milisegundos hasta el vencimiento, o `null` si no se conoce / no hay sesión. */
export function msUntilExpiry(): number | null {
  const session = readSession()
  if (!session || session.expires_at === null) return null
  return session.expires_at - EXPIRY_SKEW_MS - Date.now()
}

/**
 * Token vigente, o `null`. Si está vencido lo borra y avisa a los suscriptos
 * para que cierren la sesión en lugar de mandar un Bearer que dará 401.
 */
export function getStoredToken(): string | null {
  const session = readSession()
  if (!session) return null
  if (session.expires_at !== null && Date.now() >= session.expires_at - EXPIRY_SKEW_MS) {
    clearToken()
    notifyExpired()
    return null
  }
  return session.access_token
}

export function authHeaders(): Record<string, string> {
  const token = getStoredToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Fuerza el cierre de sesión local y avisa al resto de la app. */
export function forceLogout(): void {
  clearToken()
  notifyExpired()
}

// ── Endpoints ───────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<TokenResponse> {
  const tokens = await requestJson<TokenResponse>(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  storeSession(tokens)
  return tokens
}

export async function register(
  email: string,
  name: string,
  password: string,
): Promise<TokenResponse> {
  const tokens = await requestJson<TokenResponse>(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, name, password }),
  })
  storeSession(tokens)
  return tokens
}

export function getMe(token?: string, signal?: AbortSignal): Promise<CurrentUser> {
  const bearer = token ?? getStoredToken()
  return requestJson<CurrentUser>(`${BASE}/auth/me`, {
    headers: bearer ? { Authorization: `Bearer ${bearer}` } : {},
    signal,
  })
}

/** Cierra sesión en el backend; el borrado local ocurre igual si falla. */
export async function logout(): Promise<void> {
  try {
    await requestJson<void>(`${BASE}/auth/logout`, {
      method: 'POST',
      headers: authHeaders(),
      timeoutMs: 5_000,
    })
  } catch {
    /* el logout local es lo que importa */
  } finally {
    clearToken()
  }
}

/** URL de inicio de OAuth del backend: `GET /auth/oauth/{provider}/login`. */
export function oauthLoginUrl(provider: 'github' | 'google'): string {
  return `${BASE}/auth/oauth/${provider}/login`
}
