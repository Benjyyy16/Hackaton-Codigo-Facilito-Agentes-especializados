import { useCallback, useEffect, useRef, useState } from 'react'
import type { WsConnectionState, WsEvent } from '@/store/analysisTypes'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
const WS_URL = BACKEND_URL.replace(/^http/, 'ws') + '/ws/events'

const MAX_RECONNECT = 5
const RECONNECT_BASE_MS = 1500

interface UseWsEventsOptions {
  onEvent: (event: WsEvent) => void
  enabled?: boolean
}

export function useWsEvents({ onEvent, enabled = true }: UseWsEventsOptions) {
  const [state, setState] = useState<WsConnectionState>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const attemptsRef = useRef(0)
  const onEventRef = useRef(onEvent)
  const enabledRef = useRef(enabled)
  const mountedRef = useRef(true)

  // Actualizar refs sin re-crear la conexión
  useEffect(() => { onEventRef.current = onEvent }, [onEvent])
  useEffect(() => { enabledRef.current = enabled }, [enabled])

  const connect = useCallback(() => {
    if (!mountedRef.current) return
    if (wsRef.current && wsRef.current.readyState < 2) return // CONNECTING | OPEN

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) { ws.close(); return }
      attemptsRef.current = 0
      setState('live')
    }

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data as string) as WsEvent
        onEventRef.current(event)
      } catch {
        /* mensaje malformado — ignorar */
      }
    }

    ws.onclose = () => {
      if (!mountedRef.current) return
      if (!enabledRef.current) { setState('disconnected'); return }
      if (attemptsRef.current >= MAX_RECONNECT) {
        setState('disconnected')
        return
      }
      setState('reconnecting')
      attemptsRef.current += 1
      const delay = RECONNECT_BASE_MS * Math.pow(1.5, attemptsRef.current - 1)
      setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    if (enabled) connect()
    return () => {
      mountedRef.current = false
      wsRef.current?.close()
    }
  }, [enabled, connect])

  // Ping keepalive cada 25s
  useEffect(() => {
    const id = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 25_000)
    return () => clearInterval(id)
  }, [])

  return { wsState: state }
}
