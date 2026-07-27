/**
 * Acceso a localStorage tolerante a fallos.
 *
 * En modo privado de Safari, con la cuota llena, o con cookies de terceros
 * bloqueadas, `localStorage` lanza excepciones (o no existe). Cualquier acceso
 * directo puede tumbar la app en el primer render, así que todo pasa por aquí.
 */

let memoryFallback: Map<string, string> | null = null

function memory(): Map<string, string> {
  if (!memoryFallback) memoryFallback = new Map()
  return memoryFallback
}

/** `true` si localStorage existe y acepta escrituras. */
export function isStorageAvailable(): boolean {
  try {
    if (typeof localStorage === 'undefined') return false
    const probe = '__datgent_probe__'
    localStorage.setItem(probe, '1')
    localStorage.removeItem(probe)
    return true
  } catch {
    return false
  }
}

export function readItem(key: string): string | null {
  try {
    if (typeof localStorage === 'undefined') return memory().get(key) ?? null
    return localStorage.getItem(key)
  } catch {
    return memory().get(key) ?? null
  }
}

export function writeItem(key: string, value: string): boolean {
  try {
    if (typeof localStorage === 'undefined') throw new Error('no localStorage')
    localStorage.setItem(key, value)
    return true
  } catch {
    // Sesión sólo en memoria: se pierde al recargar, pero la app no revienta
    memory().set(key, value)
    return false
  }
}

export function removeItem(key: string): void {
  try {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(key)
  } catch {
    /* ignorado a propósito */
  }
  memory().delete(key)
}

/** Lee y parsea JSON; devuelve `null` si falta o está corrupto. */
export function readJson<T>(key: string): T | null {
  const raw = readItem(key)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    // Valor corrupto: se descarta para no repetir el fallo en cada lectura
    removeItem(key)
    return null
  }
}

export function writeJson(key: string, value: unknown): boolean {
  try {
    return writeItem(key, JSON.stringify(value))
  } catch {
    return false
  }
}
