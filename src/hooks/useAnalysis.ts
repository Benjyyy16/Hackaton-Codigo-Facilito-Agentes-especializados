import { useCallback, useEffect, useMemo, useReducer, useRef } from 'react'
import type {
  LiveSession,
  LiveAgentRecord,
  Evidence,
  LiveDecision,
  TimelineEntry,
  WsEvent,
  WsConnectionState,
  ProviderInfo,
  Alert,
  Commitment,
  CerebroState,
  RiskCase,
} from '@/store/analysisTypes'
import * as api from '@/lib/analysisApi'
import { errorMessage, isAbortError } from '@/lib/http'

// --- State ---

interface State {
  session: LiveSession | null
  sessionId: string | null
  wsState: WsConnectionState
  isRunning: boolean
  /** `true` entre el click y la respuesta de `POST /live/analysis`. */
  isStarting: boolean
  error: string | null
  provenance: ProviderInfo[]
  alerts: Alert[]
  commitments: Commitment[]
}

const initial: State = {
  session: null,
  sessionId: null,
  wsState: 'disconnected',
  isRunning: false,
  isStarting: false,
  error: null,
  provenance: [],
  alerts: [],
  commitments: [],
}

// --- Actions ---

type Action =
  | { type: 'START_PENDING' }
  | { type: 'START_OK'; sessionId: string }
  | { type: 'START_ERR'; error: string }
  | { type: 'START_CANCELLED' }
  | { type: 'SESSION_LOADED'; session: LiveSession }
  | { type: 'WS_STATE'; state: WsConnectionState }
  | { type: 'AGENT_STARTED'; agent: string }
  | { type: 'AGENT_COMPLETED'; data: Partial<LiveAgentRecord> & { agent: string } }
  | { type: 'EVIDENCE_CREATED'; evidence: Evidence }
  | { type: 'RISK_CREATED'; riskCase: RiskCase }
  | { type: 'RISK_UPDATED'; score: number; severity: string; confidence: number }
  | { type: 'ALERT_CREATED'; alert: Alert }
  | { type: 'ALERT_ACKNOWLEDGED'; alertId: string }
  | { type: 'ALERT_RESOLVED'; alertId: string }
  | { type: 'DECISION_CREATED'; decision: LiveDecision }
  | { type: 'DECISION_UPDATED'; decision: LiveDecision }
  | { type: 'DECISION_EXECUTED'; decisionId: string; status: LiveDecision['execution_status'] }
  | { type: 'COMMITMENT_STATUS_CHANGED'; commitment: Commitment }
  | { type: 'TIMELINE_APPENDED'; entry: TimelineEntry }
  | { type: 'ANALYSIS_COMPLETED'; state: CerebroState }
  | { type: 'CEREBRO_STATE_CHANGED'; cerebroState: CerebroState }
  | { type: 'PROVENANCE_LOADED'; providers: ProviderInfo[] }
  | { type: 'ERROR'; error: string }
  | { type: 'RESET' }

const TERMINAL_STATES: CerebroState[] = ['completed', 'partial_error']

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case 'START_PENDING':
      // Descarta la sesión anterior: dos sesiones vivas dejan el estado mezclado
      return {
        ...s,
        isRunning: true,
        isStarting: true,
        error: null,
        session: null,
        sessionId: null,
        alerts: [],
        commitments: [],
      }

    case 'START_OK':
      return { ...s, sessionId: a.sessionId, isStarting: false }

    case 'START_ERR':
      return { ...s, isRunning: false, isStarting: false, error: a.error }

    case 'START_CANCELLED':
      return { ...s, isRunning: false, isStarting: false }

    case 'SESSION_LOADED':
      return {
        ...s,
        session: a.session,
        sessionId: a.session.session_id ?? s.sessionId,
        isRunning: !TERMINAL_STATES.includes(a.session.state),
        isStarting: false,
      }

    case 'WS_STATE':
      return s.wsState === a.state ? s : { ...s, wsState: a.state }

    case 'AGENT_STARTED': {
      if (!s.session) return s
      const agents = s.session.agents.map((ag) =>
        ag.agent === a.agent ? { ...ag, state: 'investigating' as const } : ag,
      )
      return { ...s, session: { ...s.session, agents } }
    }

    case 'AGENT_COMPLETED': {
      if (!s.session) return s
      const agents = s.session.agents.map((ag) =>
        ag.agent === a.data.agent ? { ...ag, ...a.data } : ag,
      )
      const completed = agents.filter((ag) => ag.state === 'completed').length
      return { ...s, session: { ...s.session, agents, agents_completed: completed } }
    }

    case 'EVIDENCE_CREATED': {
      if (!s.session) return s
      return {
        ...s,
        session: {
          ...s.session,
          evidence: [...s.session.evidence, a.evidence],
          evidence_count: s.session.evidence_count + 1,
        },
      }
    }

    case 'RISK_CREATED': {
      if (!s.session) return s
      return { ...s, session: { ...s.session, risk_case: a.riskCase } }
    }

    case 'RISK_UPDATED': {
      if (!s.session?.risk_case) return s
      return {
        ...s,
        session: {
          ...s.session,
          risk_case: {
            ...s.session.risk_case,
            consolidated_score: a.score,
            severity: a.severity,
            confidence: a.confidence,
          },
        },
      }
    }

    case 'ALERT_CREATED':
      return { ...s, alerts: [...s.alerts, a.alert] }

    case 'ALERT_ACKNOWLEDGED':
      return {
        ...s,
        alerts: s.alerts.map((al) =>
          al.id === a.alertId ? { ...al, status: 'acknowledged' as const } : al,
        ),
      }

    case 'ALERT_RESOLVED':
      return {
        ...s,
        alerts: s.alerts.map((al) =>
          al.id === a.alertId ? { ...al, status: 'resolved' as const } : al,
        ),
      }

    case 'DECISION_EXECUTED': {
      if (!s.session) return s
      const decisions = s.session.decisions.map((d) =>
        d.id === a.decisionId ? { ...d, execution_status: a.status } : d,
      )
      return { ...s, session: { ...s.session, decisions } }
    }

    case 'COMMITMENT_STATUS_CHANGED': {
      const exists = s.commitments.some((c) => c.id === a.commitment.id)
      return {
        ...s,
        commitments: exists
          ? s.commitments.map((c) => (c.id === a.commitment.id ? { ...c, ...a.commitment } : c))
          : [...s.commitments, a.commitment],
      }
    }

    case 'CEREBRO_STATE_CHANGED': {
      if (!s.session) return s
      return {
        ...s,
        session: { ...s.session, state: a.cerebroState },
        isRunning: !TERMINAL_STATES.includes(a.cerebroState),
      }
    }

    case 'DECISION_CREATED': {
      if (!s.session) return s
      if (s.session.decisions.some((d) => d.id === a.decision.id)) return s
      return { ...s, session: { ...s.session, decisions: [...s.session.decisions, a.decision] } }
    }

    case 'DECISION_UPDATED': {
      if (!s.session) return s
      const known = s.session.decisions.some((d) => d.id === a.decision.id)
      const decisions = known
        ? s.session.decisions.map((d) => (d.id === a.decision.id ? a.decision : d))
        : [...s.session.decisions, a.decision]
      return { ...s, session: { ...s.session, decisions } }
    }

    case 'TIMELINE_APPENDED': {
      if (!s.session) return s
      // El polling reemite el timeline completo en cada ciclo: se deduplica
      if (a.entry.id && s.session.timeline.some((t) => t.id === a.entry.id)) return s
      return { ...s, session: { ...s.session, timeline: [...s.session.timeline, a.entry] } }
    }

    case 'ANALYSIS_COMPLETED': {
      if (!s.session) return { ...s, isRunning: false, isStarting: false }
      return {
        ...s,
        isRunning: false,
        isStarting: false,
        session: { ...s.session, state: a.state },
      }
    }

    case 'PROVENANCE_LOADED':
      return { ...s, provenance: a.providers }

    case 'ERROR':
      return { ...s, error: a.error, isRunning: false, isStarting: false }

    case 'RESET':
      // La procedencia sobrevive al reset: no depende de la sesión
      return { ...initial, provenance: s.provenance }

    default:
      return s
  }
}

// --- Hook ---

export function useAnalysis() {
  const [state, dispatch] = useReducer(reducer, initial)

  /** Espejo de `sessionId` para que los callbacks no dependan del render. */
  const sessionIdRef = useRef<string | null>(null)
  useEffect(() => {
    sessionIdRef.current = state.sessionId
  }, [state.sessionId])

  /** Cancela la request de arranque anterior al lanzar otra. */
  const startAbortRef = useRef<AbortController | null>(null)
  /** Identifica el arranque vigente: los tardíos se descartan. */
  const runTokenRef = useRef(0)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      startAbortRef.current?.abort()
      startAbortRef.current = null
    }
  }, [])

  const handleWsEvent = useCallback((event: WsEvent) => {
    switch (event.type) {
      case 'source_event.received':
      case 'pong':
        break

      case 'analysis.started':
        dispatch({ type: 'WS_STATE', state: 'live' })
        break

      case 'agent_run.started':
        dispatch({ type: 'AGENT_STARTED', agent: event.data.agent })
        break

      case 'agent_run.completed': {
        const d = event.data
        dispatch({
          type: 'AGENT_COMPLETED',
          data: {
            agent: d.agent,
            ...(d.status ? { state: d.status } : {}),
            ...(typeof d.risk_score === 'number' ? { risk_score: d.risk_score } : {}),
            ...(typeof d.severity === 'string' ? { severity: d.severity } : {}),
            ...(typeof d.confidence === 'number' ? { confidence: d.confidence } : {}),
            ...(typeof d.duration_ms === 'number' ? { duration_ms: d.duration_ms } : {}),
            ...(d.findings ? { findings_count: d.findings.length } : {}),
            ...(d.missing_information ? { missing_information: d.missing_information } : {}),
          },
        })
        break
      }

      case 'evidence.created':
        dispatch({ type: 'EVIDENCE_CREATED', evidence: event.data })
        break

      case 'risk_case.created':
        dispatch({ type: 'RISK_CREATED', riskCase: event.data })
        break

      case 'risk_case.updated':
        dispatch({
          type: 'RISK_UPDATED',
          score: event.data.consolidated_score,
          severity: event.data.severity,
          confidence: event.data.confidence,
        })
        break

      case 'alert.created':
        dispatch({ type: 'ALERT_CREATED', alert: event.data })
        break

      case 'alert.acknowledged':
        dispatch({ type: 'ALERT_ACKNOWLEDGED', alertId: event.data.id })
        break

      case 'alert.resolved':
        dispatch({ type: 'ALERT_RESOLVED', alertId: event.data.id })
        break

      case 'decision.created':
        dispatch({ type: 'DECISION_CREATED', decision: event.data })
        break

      case 'decision.updated':
      case 'decision.approved':
      case 'decision.rejected':
        dispatch({ type: 'DECISION_UPDATED', decision: event.data })
        break

      case 'decision.executed':
        dispatch({
          type: 'DECISION_EXECUTED',
          decisionId: event.data.id,
          status: event.data.execution_status,
        })
        break

      case 'commitment.status_changed':
        dispatch({ type: 'COMMITMENT_STATUS_CHANGED', commitment: event.data })
        break

      case 'timeline.appended':
        dispatch({ type: 'TIMELINE_APPENDED', entry: event.data })
        break

      case 'analysis.completed': {
        dispatch({ type: 'ANALYSIS_COMPLETED', state: event.data.state })
        // Relee la sesión completa: el evento no trae escenarios ni pre-mortem
        const sid = sessionIdRef.current
        const token = runTokenRef.current
        if (sid) {
          api
            .getSession(sid)
            .then((session) => {
              if (!mountedRef.current || token !== runTokenRef.current) return
              dispatch({ type: 'SESSION_LOADED', session })
            })
            .catch(() => {
              /* no fatal: el estado en vivo ya se aplicó */
            })
        }
        break
      }

      case 'cerebro.state_changed':
        dispatch({ type: 'CEREBRO_STATE_CHANGED', cerebroState: event.data.state })
        break
    }
  }, [])

  /**
   * Lanza un arranque cancelando el anterior. `runTokenRef` descarta cualquier
   * respuesta que llegue de un arranque ya reemplazado, que era la vía por la
   * que quedaban dos sesiones activas al cambiar de repo.
   */
  const runStart = useCallback(
    async (
      launch: (signal: AbortSignal) => Promise<api.StartAnalysisResponse>,
    ): Promise<string | null> => {
      startAbortRef.current?.abort()
      const controller = new AbortController()
      startAbortRef.current = controller
      const token = ++runTokenRef.current

      dispatch({ type: 'START_PENDING' })

      try {
        // Limpia sesiones previas del backend (sólo demo; puede no estar habilitado)
        await api.resetSessions({ signal: controller.signal }).catch(() => undefined)
        if (token !== runTokenRef.current) return null

        const { session_id } = await launch(controller.signal)
        if (!mountedRef.current || token !== runTokenRef.current) return null

        dispatch({ type: 'START_OK', sessionId: session_id })
        sessionIdRef.current = session_id
        return session_id
      } catch (err) {
        if (isAbortError(err) || token !== runTokenRef.current) {
          if (mountedRef.current && token === runTokenRef.current) {
            dispatch({ type: 'START_CANCELLED' })
          }
          return null
        }
        if (mountedRef.current) {
          dispatch({ type: 'START_ERR', error: errorMessage(err, 'No se pudo iniciar el análisis') })
        }
        return null
      } finally {
        if (startAbortRef.current === controller) startAbortRef.current = null
      }
    },
    [],
  )

  const startAnalysis = useCallback(
    () => runStart((signal) => api.startAnalysis({ signal })),
    [runStart],
  )

  const startAnalysisFromRepo = useCallback(
    (repo: api.RepoLike) => runStart((signal) => api.startAnalysisFromRepo(repo, { signal })),
    [runStart],
  )

  const simulateJira = useCallback(
    () => runStart((signal) => api.simulateJira({ signal })),
    [runStart],
  )

  /** Adopta una sesión ya creada (por ejemplo, `?session=` en la URL). */
  const attachSession = useCallback(async (sessionId: string) => {
    startAbortRef.current?.abort()
    const controller = new AbortController()
    startAbortRef.current = controller
    const token = ++runTokenRef.current
    sessionIdRef.current = sessionId

    try {
      const session = await api.getSession(sessionId, { signal: controller.signal })
      if (!mountedRef.current || token !== runTokenRef.current) return
      dispatch({ type: 'SESSION_LOADED', session })
    } catch (err) {
      if (isAbortError(err) || !mountedRef.current) return
      dispatch({ type: 'ERROR', error: errorMessage(err, 'No se pudo recuperar la sesión') })
    } finally {
      if (startAbortRef.current === controller) startAbortRef.current = null
    }
  }, [])

  const approveDecision = useCallback(async (decisionId: string, approvedBy: string) => {
    try {
      const decision = await api.approveDecision(decisionId, approvedBy)
      if (!mountedRef.current) return
      dispatch({ type: 'DECISION_UPDATED', decision })
    } catch (err) {
      if (!mountedRef.current || isAbortError(err)) return
      dispatch({ type: 'ERROR', error: errorMessage(err, 'No se pudo aprobar la decisión') })
    }
  }, [])

  const rejectDecision = useCallback(
    async (decisionId: string, rejectedBy: string, reason: string) => {
      try {
        const decision = await api.rejectDecision(decisionId, rejectedBy, reason)
        if (!mountedRef.current) return
        dispatch({ type: 'DECISION_UPDATED', decision })
      } catch (err) {
        if (!mountedRef.current || isAbortError(err)) return
        dispatch({ type: 'ERROR', error: errorMessage(err, 'No se pudo rechazar la decisión') })
      }
    },
    [],
  )

  const loadProvenance = useCallback(async () => {
    try {
      const { providers } = await api.getProvenance()
      if (!mountedRef.current) return
      dispatch({ type: 'PROVENANCE_LOADED', providers })
    } catch {
      /* la procedencia es informativa: su fallo no bloquea nada */
    }
  }, [])

  const reset = useCallback(() => {
    startAbortRef.current?.abort()
    startAbortRef.current = null
    runTokenRef.current += 1
    sessionIdRef.current = null
    dispatch({ type: 'RESET' })
  }, [])

  const setWsState = useCallback((wsState: WsConnectionState) => {
    dispatch({ type: 'WS_STATE', state: wsState })
  }, [])

  // --- Selectores memoizados ---
  // Se recalculan sólo cuando cambia la parte de la sesión que leen, en vez de
  // en cada render de la página.

  const { session } = state

  const pendingDecisions = useMemo(
    () => session?.decisions.filter((d) => d.approval_status === 'pending') ?? [],
    [session?.decisions],
  )

  const agentsProgress = useMemo(() => {
    const agents = session?.agents ?? []
    return {
      total: agents.length,
      completed: agents.filter((a) => a.state === 'completed').length,
      running: agents.filter((a) => a.state === 'investigating').length,
    }
  }, [session?.agents])

  const counters = useMemo(
    () => ({
      evidence: session?.evidence_count ?? 0,
      decisions: session?.decisions.length ?? 0,
      pendingDecisions: pendingDecisions.length,
      timeline: session?.timeline.length ?? 0,
    }),
    [session?.evidence_count, session?.decisions.length, session?.timeline.length, pendingDecisions.length],
  )

  const isDemoData = useMemo(
    () => state.provenance.some((p) => p.provenance === 'demo'),
    [state.provenance],
  )

  return {
    ...state,
    pendingDecisions,
    agentsProgress,
    counters,
    isDemoData,
    handleWsEvent,
    startAnalysis,
    startAnalysisFromRepo,
    attachSession,
    approveDecision,
    rejectDecision,
    simulateJira,
    loadProvenance,
    reset,
    setWsState,
  }
}
