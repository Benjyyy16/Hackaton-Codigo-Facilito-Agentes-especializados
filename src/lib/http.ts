/**
 * Capa HTTP común: timeout obligatorio, errores tipados y mensajes legibles.
 *
 * Sin timeout, un pre-flight CORS fallido o un backend dormido (Render tarda
 * ~30 s en despertar) deja el fetch colgado para siempre y el spinner girando.
 */

export const DEFAULT_TIMEOUT_MS = 15_000

/** Error de red / timeout / CORS: no hubo respuesta HTTP. */
export class NetworkError extends Error {
  readonly kind = 'network'
  constructor(
    message: string,
    /** `true` si el fetch se abortó por superar el timeout */
    readonly timedOut = false,
  ) {
    super(message)
    this.name = 'NetworkError'
  }
}

/** El servidor respondió con un status fuera de 2xx. */
export class HttpError extends Error {
  readonly kind = 'http'
  constructor(
    readonly status: number,
    readonly detail: string,
    readonly url: string,
  ) {
    super(detail || `HTTP ${status}`)
    this.name = 'HttpError'
  }
}

export type ApiFailure = NetworkError | HttpError

export function isHttpError(err: unknown): err is HttpError {
  return err instanceof HttpError
}

export function isNetworkError(err: unknown): err is NetworkError {
  return err instanceof NetworkError
}

/** `true` si el error viene de un aborto explícito (cambio de repo, unmount…). */
export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError'
}

/** Convierte cualquier `unknown` de un catch en un mensaje mostrable. */
export function errorMessage(err: unknown, fallback = 'Error inesperado'): string {
  if (err instanceof HttpError) {
    if (err.status === 401 || err.status === 403) return 'Tu sesión expiró. Volvé a iniciar sesión.'
    if (err.status === 404) return 'El recurso no existe en el backend.'
    if (err.status === 503) return err.detail || 'El servicio no está disponible.'
    return err.detail || `Error ${err.status}`
  }
  if (err instanceof NetworkError) return err.message
  if (err instanceof Error && err.message) return err.message
  if (typeof err === 'string' && err) return err
  return fallback
}

/** Extrae `detail` de un cuerpo de error de FastAPI, con texto crudo como respaldo. */
function extractDetail(body: string): string {
  if (!body) return ''
  try {
    const parsed: unknown = JSON.parse(body)
    if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
      const detail = (parsed as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      return JSON.stringify(detail)
    }
  } catch {
    /* no era JSON */
  }
  return body.slice(0, 300)
}

/**
 * Combina el `signal` del llamador con un timeout propio.
 * Devuelve el signal resultante y un `dispose` para limpiar listeners.
 */
function withTimeout(
  timeoutMs: number,
  external?: AbortSignal | null,
): { signal: AbortSignal; dispose: () => void; didTimeout: () => boolean } {
  const controller = new AbortController()
  let timedOut = false

  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  const onExternalAbort = () => controller.abort()
  if (external) {
    if (external.aborted) controller.abort()
    else external.addEventListener('abort', onExternalAbort, { once: true })
  }

  return {
    signal: controller.signal,
    didTimeout: () => timedOut,
    dispose: () => {
      clearTimeout(timer)
      external?.removeEventListener('abort', onExternalAbort)
    },
  }
}

export interface RequestOptions extends Omit<RequestInit, 'signal'> {
  /** Milisegundos antes de abortar. Default: 15 s. */
  timeoutMs?: number
  /** Signal del llamador (cancelar al cambiar de repo o desmontar). */
  signal?: AbortSignal | null
}

/**
 * `fetch` con timeout, parseo de errores y respuesta JSON tipada.
 * Un 204 devuelve `undefined` casteado a `T`.
 */
export async function requestJson<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: external, ...init } = options
  const guard = withTimeout(timeoutMs, external)

  let res: Response
  try {
    res = await fetch(url, { ...init, signal: guard.signal })
  } catch (err) {
    if (guard.didTimeout()) {
      throw new NetworkError(
        `El backend no respondió en ${Math.round(timeoutMs / 1000)} s. Puede estar despertando.`,
        true,
      )
    }
    // Aborto pedido por el llamador: se propaga tal cual para poder ignorarlo
    if (isAbortError(err) && external?.aborted) throw err
    throw new NetworkError('No se pudo conectar con el backend. Revisá tu conexión.')
  } finally {
    guard.dispose()
  }

  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new HttpError(res.status, extractDetail(body), url)
  }

  if (res.status === 204) return undefined as T

  const text = await res.text()
  if (!text) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    throw new HttpError(res.status, 'El backend devolvió una respuesta no-JSON', url)
  }
}
