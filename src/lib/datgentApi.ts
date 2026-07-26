/** Cliente de los endpoints de análisis de Datgent. */

import type {
  HealthResponse,
  OrchestrateResponse,
  SchemaStatus,
  Severity,
} from './datgentTypes'

const BASE_URL = 'https://hackaton-codigo-facilito-agentes.onrender.com'

/** El plan gratuito de Render duerme el servicio; despertar tarda cerca de medio minuto. */
const WAKE_UP_TIMEOUT_MS = 60_000

export class DatgentApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** `true` cuando el fallo viene de que falta el esquema en Supabase. */
    readonly schemaMissing = false,
  ) {
    super(message)
    this.name = 'DatgentApiError'
  }
}

export class DatgentNetworkError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'DatgentNetworkError'
  }
}

function extractDetail(body: unknown): string | null {
  if (typeof body !== 'object' || body === null) return null
  const record = body as Record<string, unknown>
  if (typeof record.detail === 'string') return record.detail
  const error = record.error
  if (typeof error === 'object' && error !== null) {
    const message = (error as Record<string, unknown>).message
    if (typeof message === 'string') return message
  }
  return null
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // El aborto explícito evita que la petición quede colgada cuando el servicio está
  // dormido: sin él, el usuario ve un spinner que nunca termina.
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), WAKE_UP_TIMEOUT_MS)

  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new DatgentNetworkError(
        'El servidor no respondió en 60 segundos. En el plan gratuito de Render el servicio se duerme; probá de nuevo.',
      )
    }
    throw new DatgentNetworkError(
      'No se pudo contactar con el backend. Puede estar despertando: esperá unos segundos y reintentá.',
    )
  } finally {
    window.clearTimeout(timer)
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    const detail = extractDetail(body) ?? response.statusText
    // Un 503 en los endpoints de dominio significa, casi siempre, que el esquema de
    // Supabase no está aplicado. Se marca para poder explicarlo en lugar de mostrar un
    // error genérico que no dice qué hacer.
    throw new DatgentApiError(response.status, detail, response.status === 503)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const datgent = {
  /** Ejecuta el pipeline sobre el caso de demostración. No persiste nada. */
  orchestrateDemo(): Promise<OrchestrateResponse> {
    return request<OrchestrateResponse>('/agents/orchestrate/demo', { method: 'POST' })
  },

  health(): Promise<HealthResponse> {
    return request<HealthResponse>('/health')
  },

  schemaStatus(): Promise<SchemaStatus> {
    return request<SchemaStatus>('/admin/schema/status')
  },

  /** URL del canal de eventos. `https` pasa a `wss`. */
  eventsUrl(): string {
    return `${BASE_URL.replace(/^http/, 'ws')}/ws/events`
  },
}

// ---------------------------------------------------------------------------------
// Presentación
// ---------------------------------------------------------------------------------

/** Nombres de presentación. Las claves son los identificadores del backend. */
const AGENT_LABELS: Record<string, string> = {
  'jira-agent': 'Agente Jira',
  'code-agent': 'Agente Código',
  'finance-agent': 'Agente Finanzas',
  'database-agent': 'Agente Datos',
  'orchestrator-agent': 'Datgent Cerebro',
  orchestrator: 'Datgent Cerebro',
}

const AGENT_ICONS: Record<string, string> = {
  'jira-agent': '📋',
  'code-agent': '⚙️',
  'finance-agent': '💰',
  'database-agent': '🗄️',
}

export function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] ?? agent
}

export function agentIcon(agent: string): string {
  return AGENT_ICONS[agent] ?? '🤖'
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  low: 'bajo',
  medium: 'medio',
  high: 'alto',
  critical: 'crítico',
}

/** Clases de color por severidad, coherentes con la paleta del sistema. */
export const SEVERITY_CLASSES: Record<Severity, string> = {
  low: 'border-mint-500 bg-mint-50 text-mint-700',
  medium: 'border-clay-500 bg-clay-100 text-clay-700',
  high: 'border-orange-500 bg-orange-50 text-orange-700',
  critical: 'border-rose-500 bg-rose-50 text-rose-700',
}

/**
 * Formatea un importe que llegó como texto.
 *
 * No se convierte a `number`: se inserta el separador de miles sobre la parte entera del
 * propio texto. Así un importe con más precisión que la de un `double` se muestra tal como
 * lo calculó el backend.
 */
export function formatMoney(amount: string | null, currency = 'USD'): string | null {
  if (amount === null) return null
  const [integer, decimals] = amount.split('.')
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  const symbol = currency === 'USD' ? '$' : `${currency} `
  return decimals ? `${symbol}${grouped}.${decimals}` : `${symbol}${grouped}`
}

export function formatPercent(value: number | null): string | null {
  if (value === null) return null
  return `${Math.round(value * 100)}%`
}
