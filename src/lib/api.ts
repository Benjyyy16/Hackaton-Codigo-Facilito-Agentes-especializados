const BASE_URL = 'https://hackaton-codigo-facilito-agentes.onrender.com'

const TOKEN_KEY = 'orquesta.tokens.v1'

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface AuthUser {
  id: string
  email: string
  name: string
  roles: string[]
}

// --- Token helpers ---

export function getTokens(): AuthTokens | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY)
    return raw ? (JSON.parse(raw) as AuthTokens) : null
  } catch {
    return null
  }
}

export function saveTokens(tokens: AuthTokens) {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens))
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY)
}

// --- HTTP client ---

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const tokens = getTokens()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (tokens?.access_token) {
    headers['Authorization'] = `Bearer ${tokens.access_token}`
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body?.detail ?? res.statusText)
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T

  return res.json() as Promise<T>
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

// --- Auth endpoints ---

export const api = {
  auth: {
    register(data: { email: string; name: string; password: string }) {
      return request<AuthTokens>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },

    login(data: { email: string; password: string }) {
      return request<AuthTokens>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    },

    me() {
      return request<AuthUser>('/auth/me')
    },

    logout() {
      return request<void>('/auth/logout', { method: 'POST' })
    },
  },

  health() {
    return request<{ status: string }>('/health')
  },
}
