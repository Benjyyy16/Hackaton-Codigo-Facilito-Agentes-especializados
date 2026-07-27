import { useCallback, useReducer } from 'react'
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
} from '@/store/analysisTypes'
import * as api from '@/lib/analysisApi'

// --- State ---

interface State {
  session: LiveSession | null
  sessionId: string | null
  wsState: WsConnectionState
  isRunning: boolean
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
  | { type: 'SESSION_LOADED'; session: LiveSession }
  | { type: 'WS_STATE'; state: WsConnectionState }
  | { type: 'SOURCE_EVENT_RECEIVED'; data: Record<string, unknown> }
  | { type: 'AGENT_STARTED'; agent: string }
  | { type: 'AGENT_COMPLETED'; data: Partial<LiveAgentRecord> & { agent: string } }
  | { type: 'EVIDENCE_CREATED'; evidence: Evidence }
  | { type: 'RISK_CREATED'; riskCase: Partial<LiveSession['risk_case']> }
  | { type: 'RISK_UPDATED'; score: number; severity: string; confidence: number }
  | { type: 'ALERT_CREATED'; alert: Alert }
  | { type: 'ALERT_ACKNOWLEDGED'; alertId: string }
  | { type: 'ALERT_RESOLVED'; alertId: string }
  | { type: 'DECISION_CREATED'; decision: LiveDecision }
  | { type: 'DECISION_UPDATED'; decision: LiveDecision }
  | { type: 'DECISION_EXECUTED'; decisionId: string; status: string }
  | { type: 'COMMITMENT_STATUS_CHANGED'; commitment: Commitment }
  | { type: 'TIMELINE_APPENDED'; entry: TimelineEntry }
  | { type: 'ANALYSIS_COMPLETED'; state: string; score: number }
  | { type: 'CEREBRO_STATE_CHANGED'; cerebroState: CerebroState }
  | { type: 'PROVENANCE_LOADED'; providers: ProviderInfo[] }
  | { type: 'RESET' }

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case 'START_PENDING':
      return { ...s, isRunning: true, error: null, session: null, sessionId: null }

    case 'START_OK':
      return { ...s, sessionId: a.sessionId }

    case 'START_ERR':
      return { ...s, isRunning: false, error: a.error }

    case 'SESSION_LOADED':
      return {
        ...s,
        session: a.session,
        isRunning: !['completed', 'partial_error'].includes(a.session.state),
      }

    case 'WS_STATE':
      return { ...s, wsState: a.state }

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
      return {
        ...s,
        session: { ...s.session, agents, agents_completed: completed },
      }
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

    case 'RISK_UPDATED': {
      if (!s.session) return s
      const rc = s.session.risk_case
      return {
        ...s,
        session: {
          ...s.session,
          risk_case: rc
            ? { ...rc, consolidated_score: a.score, severity: a.severity, confidence: a.confidence }
            : null,
        },
      }
    }

    case 'SOURCE_EVENT_RECEIVED': {
      // source_event.received — noop para state, puede usarse para logging
      return s
    }

    case 'RISK_CREATED': {
      if (!s.session) return s
      return {
        ...s,
        session: {
          ...s.session,
          risk_case: (a.riskCase ?? null) as LiveSession['risk_case'],
        },
      }
    }

    case 'ALERT_CREATED': {
      return { ...s, alerts: [...s.alerts, a.alert] }
    }

    case 'ALERT_ACKNOWLEDGED': {
      const alerts = s.alerts.map((al) =>
        al.id === a.alertId ? { ...al, status: 'acknowledged' as const } : al,
      )
      return { ...s, alerts }
    }

    case 'ALERT_RESOLVED': {
      const alerts = s.alerts.map((al) =>
        al.id === a.alertId ? { ...al, status: 'resolved' as const } : al,
      )
      return { ...s, alerts }
    }

    case 'DECISION_EXECUTED': {
      if (!s.session) return s
      const decisions = s.session.decisions.map((d) =>
        d.id === a.decisionId
          ? { ...d, execution_status: a.status as LiveDecision['execution_status'] }
          : d,
      )
      return { ...s, session: { ...s.session, decisions } }
    }

    case 'COMMITMENT_STATUS_CHANGED': {
      const commitments = s.commitments.map((c) =>
        c.id === a.commitment.id ? { ...c, ...a.commitment } : c,
      )
      // Si no existe, agregarlo
      const exists = s.commitments.some((c) => c.id === a.commitment.id)
      return { ...s, commitments: exists ? commitments : [...s.commitments, a.commitment] }
    }

    case 'CEREBRO_STATE_CHANGED': {
      if (!s.session) return s
      return {
        ...s,
        session: { ...s.session, state: a.cerebroState },
        isRunning: !['completed', 'partial_error'].includes(a.cerebroState),
      }
    }

    case 'DECISION_CREATED': {
      if (!s.session) return s
      return {
        ...s,
        session: {
          ...s.session,
          decisions: [...s.session.decisions, a.decision],
        },
      }
    }

    case 'DECISION_UPDATED': {
      if (!s.session) return s
      const decisions = s.session.decisions.map((d) =>
        d.id === a.decision.id ? a.decision : d,
      )
      return { ...s, session: { ...s.session, decisions } }
    }

    case 'TIMELINE_APPENDED': {
      if (!s.session) return s
      return {
        ...s,
        session: {
          ...s.session,
          timeline: [...s.session.timeline, a.entry],
        },
      }
    }

    case 'ANALYSIS_COMPLETED': {
      if (!s.session) return s
      return {
        ...s,
        isRunning: false,
        session: { ...s.session, state: a.state as LiveSession['state'] },
      }
    }

    case 'PROVENANCE_LOADED':
      return { ...s, provenance: a.providers }

    case 'RESET':
      return { ...initial }

    default:
      return s
  }
}

// --- Hook ---

export function useAnalysis() {
  const [state, dispatch] = useReducer(reducer, initial)

  const handleWsEvent = useCallback((event: WsEvent) => {
    const d = event.data
    switch (event.type) {
      case 'source_event.received':
        dispatch({ type: 'SOURCE_EVENT_RECEIVED', data: d })
        break

      case 'analysis.started':
        dispatch({ type: 'WS_STATE', state: 'live' })
        break

      case 'agent_run.started':
        dispatch({ type: 'AGENT_STARTED', agent: d.agent as string })
        break

      case 'agent_run.completed':
        dispatch({
          type: 'AGENT_COMPLETED',
          data: {
            agent: d.agent as string,
            state: d.status as LiveAgentRecord['state'],
            risk_score: d.risk_score as number,
            severity: d.severity as string,
            confidence: d.confidence as number,
            findings_count: (d.findings as unknown[])?.length ?? 0,
            duration_ms: d.duration_ms as number,
          },
        })
        break

      case 'evidence.created':
        dispatch({ type: 'EVIDENCE_CREATED', evidence: d as unknown as Evidence })
        break

      case 'risk_case.created':
        dispatch({ type: 'RISK_CREATED', riskCase: d as unknown as Partial<LiveSession['risk_case']> })
        break

      case 'risk_case.updated':
        dispatch({
          type: 'RISK_UPDATED',
          score: d.consolidated_score as number,
          severity: d.severity as string,
          confidence: d.confidence as number,
        })
        break

      case 'alert.created':
        dispatch({ type: 'ALERT_CREATED', alert: d as unknown as Alert })
        break

      case 'alert.acknowledged':
        dispatch({ type: 'ALERT_ACKNOWLEDGED', alertId: d.id as string })
        break

      case 'alert.resolved':
        dispatch({ type: 'ALERT_RESOLVED', alertId: d.id as string })
        break

      case 'decision.created':
        dispatch({ type: 'DECISION_CREATED', decision: d as unknown as LiveDecision })
        break

      case 'decision.updated':
        dispatch({ type: 'DECISION_UPDATED', decision: d as unknown as LiveDecision })
        break

      case 'decision.executed':
        dispatch({ type: 'DECISION_EXECUTED', decisionId: d.id as string, status: d.execution_status as string })
        break

      case 'commitment.status_changed':
        dispatch({ type: 'COMMITMENT_STATUS_CHANGED', commitment: d as unknown as Commitment })
        break

      case 'timeline.appended':
        dispatch({ type: 'TIMELINE_APPENDED', entry: d as unknown as TimelineEntry })
        break

      case 'analysis.completed':
        dispatch({
          type: 'ANALYSIS_COMPLETED',
          state: d.state as string,
          score: d.consolidated_score as number,
        })
        // Fetch sesión completa al finalizar para tener risk_case con escenarios
        if (state.sessionId) {
          api.getSession(state.sessionId).then((session) => {
            dispatch({ type: 'SESSION_LOADED', session })
          }).catch(() => { /* no fatal */ })
        }
        break

      case 'cerebro.state_changed':
        dispatch({ type: 'CEREBRO_STATE_CHANGED', cerebroState: d.state as CerebroState })
        break
    }
  }, [state.sessionId])

  const startAnalysis = useCallback(async () => {
    dispatch({ type: 'START_PENDING' })
    try {
      // Intentar resetear sesiones previas (solo en demo, puede fallar en prod → ignorar)
      await api.resetSessions().catch(() => { /**/ })
      const { session_id } = await api.startAnalysis()
      dispatch({ type: 'START_OK', sessionId: session_id })
    } catch (err) {
      dispatch({ type: 'START_ERR', error: err instanceof Error ? err.message : String(err) })
    }
  }, [])

  const approveDecision = useCallback(
    async (decisionId: string, approvedBy: string) => {
      const decision = await api.approveDecision(decisionId, approvedBy)
      dispatch({ type: 'DECISION_UPDATED', decision })
    },
    [],
  )

  const rejectDecision = useCallback(
    async (decisionId: string, rejectedBy: string, reason: string) => {
      const decision = await api.rejectDecision(decisionId, rejectedBy, reason)
      dispatch({ type: 'DECISION_UPDATED', decision })
    },
    [],
  )

  const simulateJira = useCallback(async () => {
    dispatch({ type: 'START_PENDING' })
    try {
      await api.resetSessions().catch(() => { /**/ })
      const { session_id } = await api.simulateJira()
      dispatch({ type: 'START_OK', sessionId: session_id })
    } catch (err) {
      dispatch({ type: 'START_ERR', error: err instanceof Error ? err.message : String(err) })
    }
  }, [])

  const loadProvenance = useCallback(async () => {
    try {
      const { providers } = await api.getProvenance()
      dispatch({ type: 'PROVENANCE_LOADED', providers })
    } catch { /**/ }
  }, [])

  const reset = useCallback(() => dispatch({ type: 'RESET' }), [])

  const setWsState = useCallback((wsState: WsConnectionState) => {
    dispatch({ type: 'WS_STATE', state: wsState })
  }, [])

  return {
    ...state,
    handleWsEvent,
    startAnalysis,
    approveDecision,
    rejectDecision,
    simulateJira,
    loadProvenance,
    reset,
    setWsState,
  }
}
