import { useCallback, useEffect, useRef, useState } from 'react'
import { datgent } from '@/lib/datgentApi'
import type { WsEvent } from '@/lib/datgentTypes'

export type ConnectionState = 'connecting' | 'open' | 'closed' | 'error'

/** Eventos que se conservan en memoria. Por encima, los viejos se descartan. */
const MAX_EVENTS = 50

/** Espera antes de reintentar. Fija y no exponencial: el canal es de un solo servicio. */
const RECONNECT_DELAY_MS = 5_000

/** Latido. Render corta las conexiones inactivas, así que hay que dar señal de vida. */
const PING_INTERVAL_MS = 30_000

interface UseDatgentEventsResult {
  events: WsEvent[]
  state: ConnectionState
  clear: () => void
}

/**
 * Suscribe al canal de eventos del backend.
 *
 * Reconecta solo cuando el cierre no fue intencionado. Distinguirlo importa: sin esa
 * comprobación, desmontar el componente abriría una conexión nueva justo después de
 * cerrar la anterior, y el ciclo no pararía nunca.
 *
 * Los mensajes que no son JSON válido se ignoran en silencio. El servidor responde
 * `{"type":"pong"}` al latido, y eso no es un evento de dominio: se filtra.
 */
export function useDatgentEvents(enabled = true): UseDatgentEventsResult {
  const [events, setEvents] = useState<WsEvent[]>([])
  const [state, setState] = useState<ConnectionState>('closed')

  const socketRef = useRef<WebSocket | null>(null)
  const reconnectRef = useRef<number | null>(null)
  const pingRef = useRef<number | null>(null)
  /** Marca el desmontaje para no reconectar tras un cierre intencionado. */
  const intentionalCloseRef = useRef(false)

  const clear = useCallback(() => setEvents([]), [])

  useEffect(() => {
    if (!enabled) return

    intentionalCloseRef.current = false

    const connect = () => {
      setState('connecting')

      let socket: WebSocket
      try {
        socket = new WebSocket(datgent.eventsUrl())
      } catch {
        setState('error')
        return
      }
      socketRef.current = socket

      socket.onopen = () => {
        setState('open')
        pingRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send('ping')
        }, PING_INTERVAL_MS)
      }

      socket.onmessage = (message) => {
        let parsed: unknown
        try {
          parsed = JSON.parse(message.data as string)
        } catch {
          return
        }
        if (typeof parsed !== 'object' || parsed === null) return

        const candidate = parsed as Partial<WsEvent>
        // El pong del latido no es un evento de dominio.
        if (!candidate.type || candidate.type === 'pong') return

        setEvents((previous) => [candidate as WsEvent, ...previous].slice(0, MAX_EVENTS))
      }

      socket.onerror = () => setState('error')

      socket.onclose = () => {
        if (pingRef.current !== null) {
          window.clearInterval(pingRef.current)
          pingRef.current = null
        }
        setState('closed')
        if (!intentionalCloseRef.current) {
          reconnectRef.current = window.setTimeout(connect, RECONNECT_DELAY_MS)
        }
      }
    }

    connect()

    return () => {
      intentionalCloseRef.current = true
      if (reconnectRef.current !== null) window.clearTimeout(reconnectRef.current)
      if (pingRef.current !== null) window.clearInterval(pingRef.current)
      socketRef.current?.close()
    }
  }, [enabled])

  return { events, state, clear }
}
