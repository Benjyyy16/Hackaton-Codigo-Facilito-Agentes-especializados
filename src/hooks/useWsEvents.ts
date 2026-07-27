import { useCallback, useEffect, useRef, useState } from 'react'
import type { WsConnectionState, WsEvent } from '@/store/analysisTypes'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
const WS_URL = BACKEND_URL.replace(/^http/, 'ws') + '/ws/events'

const MAX_RECONNECT = 3
const RECONNECT_BASE_MS = 2000
/** Si WS falla MAX_RECONNECT veces, activa polling cada POLL_INTERVAL_MS */
const POLL_INTERVAL_MS = 2500

interface UseWsEventsOptions {
  onEvent: (event: WsEvent) => void
  /** session_id activo para polling */
  sessionId?: string | null
  enabled?: boolean
}

export function useWsEvents({ onEvent, sessionId, enabled = true }: UseWsEventsOptions) {
  const [state, setState] = useState<WsConnectionState>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const attemptsRef = useRef(0)
  const onEventRef = useRef(onEvent)
  const enabledRef = useRef(enabled)
  const mountedRef = useRef(true)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const usingPollingRef = useRef(false)
  const lastEvidenceCount = useRef(0)
  const sessionIdRef = useRef(sessionId)

  useEffect(() => { onEventRef.current = onEvent }, [onEvent])
  useEffect(() => { enabledRef.current = enabled }, [enabled])
  useEffect(() => { sessionIdRef.current = sessionId }, [sessionId])

  // ── Polling fallback ──────────────────────────────────────────────
  const startPolling = useCallback(() => {
    if (pollingRef.current) return
    usingPollingRef.current = true
    setState('live') // polling = "en vivo" a efectos del UI

    pollingRef.current = setInterval(async () => {
      const sid = sessionIdRef.current
      if (!sid || !mountedRef.current) return
      try {
        const res = await fetch(`${BACKEND_URL}/live/analysis/${sid}`)
        if (!res.ok) return
        const session = await res.json()
        // Emular eventos WS a partir del diff de estado
        onEventRef.current({ type: 'analysis.started', data: { session_id: sid } })
        // Emitir agentes completados
        for (const ag of session.agents ?? []) {
          if (ag.state !== 'waiting') {
            onEventRef.current({
              type: 'agent_run.completed',
              data: {
                agent: ag.agent,
                status: ag.state,
                risk_score: ag.risk_score,
                severity: ag.severity,
                confidence: ag.confidence,
                findings: [],
                duration_ms: ag.duration_ms,
              },
            })
          }
        }
        // Emitir evidencias nuevas
        const evidences = session.evidence ?? []
        if (evidences.length > lastEvidenceCount.current) {
          for (let i = lastEvidenceCount.current; i < evidences.length; i++) {
            onEventRef.current({ type: 'evidence.created', data: evidences[i] })
          }
          lastEvidenceCount.current = evidences.length
        }
        // Risk case
        if (session.risk_case) {
          onEventRef.current({
            type: 'risk_case.updated',
            data: {
              consolidated_score: session.risk_case.consolidated_score,
              severity: session.risk_case.severity,
              confidence: session.risk_case.confidence,
            },
          })
        }
        // Decisiones
        for (const d of session.decisions ?? []) {
          onEventRef.current({ type: 'decision.updated', data: d })
        }
        // Timeline
        for (const t of session.timeline ?? []) {
          onEventRef.current({ type: 'timeline.appended', data: t })
        }
        // Completado
        if (['completed', 'partial_error', 'awaiting_approval'].includes(session.state)) {
          onEventRef.current({
            type: 'analysis.completed',
            data: { state: session.state, consolidated_score: session.risk_case?.consolidated_score ?? 0 },
          })
          // Parar polling si terminó
          if (session.state !== 'awaiting_approval') {
            stopPolling()
          }
        }
      } catch {
        /* red — continuar */
      }
    }, POLL_INTERVAL_MS)
  }, [])

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  // ── WebSocket ─────────────────────────────────────────────────────
  const connect = useCallback(() => {
    if (!mountedRef.current) return
    if (wsRef.current && wsRef.current.readyState < 2) return

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return }
      attemptsRef.current = 0
      usingPollingRef.current = false
      stopPolling()
      setState('live')
    }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data as string) as WsEvent
        onEventRef.current(event)
      } catch { /**/ }
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      if (!enabledRef.current) { setState('disconnected'); return }

      if (attemptsRef.current >= MAX_RECONNECT) {
        // WS no disponible — usar polling
        setState('live') // sigue "en vivo" vía polling
        startPolling()
        return
      }
      setState('reconnecting')
      attemptsRef.current += 1
      const delay = RECONNECT_BASE_MS * Math.pow(1.5, attemptsRef.current - 1)
      setTimeout(connect, delay)
    }

    ws.onerror = () => ws.close()
  }, [startPolling, stopPolling])

  useEffect(() => {
    mountedRef.current = true
    if (enabled) connect()
    return () => {
      mountedRef.current = false
      wsRef.current?.close()
      stopPolling()
    }
  }, [enabled, connect, stopPolling])

  // Reiniciar polling cuando llega un nuevo sessionId
  useEffect(() => {
    if (usingPollingRef.current && sessionId) {
      lastEvidenceCount.current = 0
    }
  }, [sessionId])

  // Ping keepalive WS
  useEffect(() => {
    const id = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 25_000)
    return () => clearInterval(id)
  }, [])

  return { wsState: state, usingPolling: usingPollingRef.current }
}
