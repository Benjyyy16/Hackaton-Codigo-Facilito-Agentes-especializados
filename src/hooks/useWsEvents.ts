import { useCallback, useEffect, useRef, useState } from 'react'
import { parseWsEvent, type LiveSession, type WsConnectionState, type WsEvent } from '@/store/analysisTypes'
import { requestJson } from '@/lib/http'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
const WS_URL = BACKEND_URL.replace(/^http/, 'ws') + '/ws/events'

/** Reintentos de WebSocket antes de degradar a polling. */
const MAX_RECONNECT = 3
const RECONNECT_BASE_MS = 2_000
const POLL_INTERVAL_MS = 2_500
const PING_INTERVAL_MS = 25_000

/** Un poll no puede durar más que unos pocos ciclos: si tarda, se descarta. */
const POLL_TIMEOUT_MS = 8_000

/**
 * Presupuesto total desde el primer fallo. Si en este tiempo no se logró una
 * conexión ni un poll exitoso, se declara el backend caído y se dejan de
 * consumir recursos: antes el polling seguía para siempre.
 */
const OFFLINE_AFTER_MS = 60_000

/** Polls consecutivos fallidos que también fuerzan el estado offline. */
const MAX_POLL_FAILURES = 6

interface UseWsEventsOptions {
  onEvent: (event: WsEvent) => void
  /** session_id activo, usado por el polling de respaldo. */
  sessionId?: string | null
  enabled?: boolean
}

interface UseWsEventsResult {
  wsState: WsConnectionState
  /** `true` si los eventos llegan por polling y no por WebSocket. */
  usingPolling: boolean
  /** Reinicia el ciclo de conexión desde cero (botón "Reintentar"). */
  retry: () => void
}

/**
 * Canal de eventos en vivo con degradación controlada:
 * WebSocket → polling → offline.
 *
 * Todo el ciclo de vida (socket, timers, fetch en vuelo) vive dentro de un
 * único efecto, así el cleanup no puede quedarse a medias aunque el componente
 * se desmonte durante el handshake.
 */
export function useWsEvents({
  onEvent,
  sessionId,
  enabled = true,
}: UseWsEventsOptions): UseWsEventsResult {
  const [state, setState] = useState<WsConnectionState>('disconnected')
  const [usingPolling, setUsingPolling] = useState(false)
  const [retryNonce, setRetryNonce] = useState(0)

  const onEventRef = useRef(onEvent)
  const sessionIdRef = useRef(sessionId)
  const lastEvidenceCount = useRef(0)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    sessionIdRef.current = sessionId
    // Sesión nueva: el polling debe reemitir sus evidencias desde el principio
    lastEvidenceCount.current = 0
  }, [sessionId])

  const retry = useCallback(() => {
    lastEvidenceCount.current = 0
    setState('reconnecting')
    setRetryNonce((n) => n + 1)
  }, [])

  useEffect(() => {
    if (!enabled) {
      setState('disconnected')
      setUsingPolling(false)
      return
    }

    /** Marca el desmontaje: ningún callback tardío debe tocar el estado. */
    let cancelled = false
    const abort = new AbortController()
    const timers = new Set<ReturnType<typeof setTimeout>>()
    let socket: WebSocket | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let pingTimer: ReturnType<typeof setInterval> | null = null
    let attempts = 0
    let pollFailures = 0
    let firstFailureAt: number | null = null

    const schedule = (fn: () => void, ms: number) => {
      const id = setTimeout(() => {
        timers.delete(id)
        if (!cancelled) fn()
      }, ms)
      timers.add(id)
    }

    const stopPolling = () => {
      if (pollTimer !== null) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }

    const markFailure = () => {
      if (firstFailureAt === null) firstFailureAt = Date.now()
    }

    const budgetExhausted = () =>
      firstFailureAt !== null && Date.now() - firstFailureAt >= OFFLINE_AFTER_MS

    const goOffline = () => {
      if (cancelled) return
      stopPolling()
      setUsingPolling(false)
      setState('offline')
    }

    const emit = (event: WsEvent) => {
      if (cancelled) return
      onEventRef.current(event)
    }

    // ── Polling de respaldo ─────────────────────────────────────────
    const pollOnce = async () => {
      const sid = sessionIdRef.current
      if (cancelled) return
      if (!sid) {
        // Sin sesión no hay nada que consultar, pero el WS sigue caído: si se
        // agota el presupuesto hay que decir la verdad en lugar de "en vivo"
        if (budgetExhausted()) goOffline()
        return
      }

      try {
        // Timeout propio además del signal de cleanup: un poll colgado no debe
        // solaparse con los siguientes ni sobrevivir al desmontaje
        const session = await requestJson<LiveSession>(
          `${BACKEND_URL}/live/analysis/${sid}`,
          { signal: abort.signal, timeoutMs: POLL_TIMEOUT_MS },
        )
        if (cancelled) return

        pollFailures = 0
        firstFailureAt = null
        // Polling con respuesta = datos frescos: para el usuario es "en vivo"
        setState('live')

        emit({ type: 'analysis.started', data: { session_id: sid } })

        for (const agent of session.agents ?? []) {
          if (agent.state === 'waiting') continue
          emit({
            type: 'agent_run.completed',
            data: {
              agent: agent.agent,
              status: agent.state,
              risk_score: agent.risk_score,
              severity: agent.severity,
              confidence: agent.confidence,
              duration_ms: agent.duration_ms,
            },
          })
        }

        const evidence = session.evidence ?? []
        if (evidence.length > lastEvidenceCount.current) {
          for (let i = lastEvidenceCount.current; i < evidence.length; i++) {
            emit({ type: 'evidence.created', data: evidence[i] })
          }
          lastEvidenceCount.current = evidence.length
        }

        if (session.risk_case) {
          emit({
            type: 'risk_case.updated',
            data: {
              consolidated_score: session.risk_case.consolidated_score,
              severity: session.risk_case.severity,
              confidence: session.risk_case.confidence,
            },
          })
        }

        for (const decision of session.decisions ?? []) {
          emit({ type: 'decision.updated', data: decision })
        }
        for (const entry of session.timeline ?? []) {
          emit({ type: 'timeline.appended', data: entry })
        }

        if (['completed', 'partial_error', 'awaiting_approval'].includes(session.state)) {
          emit({ type: 'analysis.completed', data: { state: session.state } })
          if (session.state !== 'awaiting_approval') stopPolling()
        }
      } catch {
        if (cancelled) return
        markFailure()
        pollFailures += 1
        if (pollFailures >= MAX_POLL_FAILURES || budgetExhausted()) goOffline()
      }
    }

    const startPolling = () => {
      if (cancelled || pollTimer !== null) return
      setUsingPolling(true)
      // Aún no se sabe si el polling responde: no se anuncia "en vivo" todavía
      setState('reconnecting')
      void pollOnce()
      pollTimer = setInterval(() => void pollOnce(), POLL_INTERVAL_MS)
    }

    // ── WebSocket ───────────────────────────────────────────────────
    const detach = (ws: WebSocket) => {
      ws.onopen = null
      ws.onmessage = null
      ws.onclose = null
      ws.onerror = null
    }

    const connect = () => {
      if (cancelled) return

      let ws: WebSocket
      try {
        ws = new WebSocket(WS_URL)
      } catch {
        markFailure()
        startPolling()
        return
      }
      socket = ws

      ws.onopen = () => {
        // El desmontaje puede ocurrir durante el handshake
        if (cancelled) {
          detach(ws)
          ws.close()
          return
        }
        attempts = 0
        pollFailures = 0
        firstFailureAt = null
        stopPolling()
        setUsingPolling(false)
        setState('live')
      }

      ws.onmessage = (e) => {
        if (cancelled) return
        let raw: unknown
        try {
          raw = JSON.parse(typeof e.data === 'string' ? e.data : '')
        } catch {
          return
        }
        const event = parseWsEvent(raw)
        if (!event || event.type === 'pong') return
        emit(event)
      }

      ws.onerror = () => {
        // `onclose` siempre llega después: la reconexión se maneja allí
        try {
          ws.close()
        } catch {
          /* ya cerrado */
        }
      }

      ws.onclose = () => {
        if (cancelled) return
        detach(ws)
        if (socket === ws) socket = null

        markFailure()

        if (budgetExhausted()) {
          goOffline()
          return
        }

        if (attempts >= MAX_RECONNECT) {
          // WS no disponible en este entorno: se degrada a polling
          startPolling()
          // El presupuesto sigue corriendo; si el polling tampoco responde → offline
          schedule(() => {
            if (!cancelled && budgetExhausted()) goOffline()
          }, OFFLINE_AFTER_MS)
          return
        }

        attempts += 1
        setState('reconnecting')
        schedule(connect, RECONNECT_BASE_MS * Math.pow(1.5, attempts - 1))
      }
    }

    connect()

    pingTimer = setInterval(() => {
      if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
    }, PING_INTERVAL_MS)

    return () => {
      cancelled = true
      for (const id of timers) clearTimeout(id)
      timers.clear()
      stopPolling()
      if (pingTimer !== null) clearInterval(pingTimer)
      abort.abort()
      if (socket) {
        detach(socket)
        try {
          socket.close()
        } catch {
          /* ya cerrado */
        }
        socket = null
      }
    }
  }, [enabled, retryNonce])

  return { wsState: state, usingPolling, retry }
}
