import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Brain,
  Code2,
  Database,
  Landmark,
  Play,
  Zap,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CloudOff,
  RotateCw,
  Ticket,
} from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { AnalysisTerminal } from '@/components/app/CompanyAiChat'
import { Button } from '@/components/ui/Button'
import { WsIndicator } from '@/components/datgent/WsIndicator'
import { CerebroPanel } from '@/components/datgent/CerebroPanel'
import { AgentCard } from '@/components/datgent/AgentCard'
import { EvidenceList } from '@/components/datgent/EvidenceList'
import { DecisionPanel } from '@/components/datgent/DecisionPanel'
import { TimelineView } from '@/components/datgent/TimelineView'
import { ProvenanceBanner } from '@/components/datgent/ProvenanceBanner'
import { CardSkeleton, LoadingRegion } from '@/components/ui/Skeleton'
import { useAnalysis } from '@/hooks/useAnalysis'
import { useWsEvents } from '@/hooks/useWsEvents'
import { useAppStore } from '@/store/AppStore'

type Tab = 'agentes' | 'evidencias' | 'decisiones' | 'timeline'

const tabs: { id: Tab; label: string }[] = [
  { id: 'agentes', label: 'Agentes' },
  { id: 'evidencias', label: 'Evidencias' },
  { id: 'decisiones', label: 'Decisiones' },
  { id: 'timeline', label: 'Timeline' },
]

const showcaseAgents = [
  { name: 'Agente Jira', score: 90, meta: '4 hallazgos · confianza 94%', sev: 'crítico', Icon: Ticket, cls: 'text-violet-600 bg-violet-50' },
  { name: 'Agente Código', score: 85, meta: '7 hallazgos · confianza 95%', sev: 'crítico', Icon: Code2, cls: 'text-ink-700 bg-ink-100' },
  { name: 'Agente Finanzas', score: 100, meta: '3 hallazgos · confianza 81%', sev: 'crítico', Icon: Landmark, cls: 'text-clay-700 bg-clay-100' },
  { name: 'Agente Datos', score: 75, meta: '1 hallazgo · confianza 100%', sev: 'alto', Icon: Database, cls: 'text-mint-700 bg-mint-50' },
] as const

function AgentShowcaseCards() {
  return (
    <div>
      <div className="mb-4">
        <h2 className="font-display text-[30px] leading-none text-ink-900">Agentes</h2>
        <p className="mt-2 text-[14px] text-ink-500">
          Un agente sin señal de su proveedor no inventa: muestra qué no pudo mirar.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {showcaseAgents.map(({ name, score, meta, sev, Icon, cls }) => (
          <article
            key={name}
            className="group rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard-sm transition-transform hover:-translate-y-1 hover:border-violet-600"
          >
            <div className="flex items-start justify-between">
              <span
                className={`grid h-12 w-12 place-items-center rounded-lg border-2 border-ink-900 ${cls} transition-transform group-hover:-rotate-6`}
              >
                <Icon className="h-6 w-6" />
              </span>
              <span className="rounded-full border border-clay-400 bg-clay-50 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-clay-700">
                {sev}
              </span>
            </div>
            <h3 className="mt-8 text-[19px] font-extrabold text-ink-900">{name}</h3>
            <p className="mt-3 font-display text-[38px] leading-none text-ink-900">
              {score}<span className="text-[14px] text-ink-300">/100</span>
            </p>
            <p className="mt-4 font-mono text-[11px] text-ink-500">{meta}</p>
            <div className="mt-5 h-px border-t-2 border-dashed border-ink-100" />
            <p className="mt-4 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-700">
              Ver evidencia →
            </p>
          </article>
        ))}
      </div>
    </div>
  )
}

export default function DatgentAnalysis() {
  const [tab, setTab] = useState<Tab>('agentes')
  const [showScenarios, setShowScenarios] = useState(false)
  const [searchParams] = useSearchParams()
  const { user } = useAppStore()

  const analysis = useAnalysis()
  const {
    session,
    sessionId,
    isRunning,
    isStarting,
    error,
    provenance,
    counters,
    isDemoData,
    handleWsEvent,
    startAnalysis,
    startAnalysisFromRepo,
    attachSession,
    simulateJira,
    loadProvenance,
    reset,
    setWsState,
    approveDecision,
    rejectDecision,
  } = analysis

  const repoParam = searchParams.get('repo')
  const sessionParam = searchParams.get('session')

  /**
   * Los parámetros de URL se atienden una sola vez por valor.
   *
   * Antes el efecto dependía del objeto `analysis` y de `isRunning`, así que
   * cualquier cambio de estado lo re-ejecutaba y podía disparar un análisis
   * nuevo en bucle. Con el ref, el disparo depende sólo del valor de la URL.
   */
  const handledParamRef = useRef<string | null>(null)

  useEffect(() => {
    const key = sessionParam ? `session:${sessionParam}` : repoParam ? `repo:${repoParam}` : null
    if (!key || handledParamRef.current === key) return
    handledParamRef.current = key

    if (sessionParam) {
      void attachSession(sessionParam)
    } else if (repoParam) {
      void startAnalysisFromRepo({ full_name: repoParam })
    }
  }, [repoParam, sessionParam, attachSession, startAnalysisFromRepo])

  // El WS se mantiene abierto: los eventos de decisiones llegan también
  // después de que el análisis terminó
  const { wsState, usingPolling, retry } = useWsEvents({
    onEvent: handleWsEvent,
    sessionId,
    enabled: true,
  })

  useEffect(() => {
    setWsState(wsState)
  }, [wsState, setWsState])

  useEffect(() => {
    void loadProvenance()
  }, [loadProvenance])

  // Al llegar a aprobación, la pestaña útil es Decisiones
  const sessionState = session?.state
  useEffect(() => {
    if (sessionState === 'awaiting_approval') setTab('decisiones')
  }, [sessionState])

  const cerebroState = sessionState ?? 'ready'
  const isOffline = wsState === 'offline'

  const approver = user?.name ?? 'usuario'
  const onApprove = useCallback(
    (decisionId: string) => approveDecision(decisionId, approver),
    [approveDecision, approver],
  )
  const onReject = useCallback(
    (decisionId: string, _by: string, reason: string) =>
      rejectDecision(decisionId, approver, reason),
    [rejectDecision, approver],
  )

  const scenarios = session?.risk_case?.scenarios
  const causalChain = session?.risk_case?.causal_chain
  const premortem = session?.risk_case?.premortem

  const tabBadges = useMemo<Record<Tab, number>>(
    () => ({
      agentes: 0,
      evidencias: counters.evidence,
      decisiones: counters.pendingDecisions,
      timeline: 0,
    }),
    [counters.evidence, counters.pendingDecisions],
  )

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-8 sm:py-7">
        {/* ─── Encabezado ─── */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border-2 border-ink-900 bg-paper shadow-hard-sm">
                <Brain className="h-4 w-4 text-violet-600" aria-hidden />
              </div>
              <h1 className="font-display text-[28px] leading-none tracking-tightest text-ink-900 sm:text-[38px]">
                Datgent
              </h1>
            </div>
            <p className="mt-1.5 text-[12.5px] text-ink-500 sm:text-[13px]">
              Análisis multiagente de compromisos en riesgo
            </p>
          </div>

          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <WsIndicator state={wsState} />
            {usingPolling && (
              <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
                vía polling
              </span>
            )}

            {!isRunning && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => void simulateJira()}
                title="Simula un evento Jira crítico (solo demo)"
                aria-label="Simular evento crítico de Jira"
              >
                <Zap className="h-3.5 w-3.5" aria-hidden />
                Simular Jira
              </Button>
            )}

            {session && !isRunning && (
              <Button size="sm" variant="ghost" onClick={reset} aria-label="Limpiar análisis">
                <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                Limpiar
              </Button>
            )}

            <Button
              size="sm"
              variant="primary"
              loading={isRunning}
              disabled={isRunning}
              onClick={() => void startAnalysis()}
              aria-label="Analizar compromiso"
            >
              <Play className="h-3.5 w-3.5" aria-hidden />
              {isStarting ? 'Iniciando…' : isRunning ? 'Analizando…' : 'Analizar compromiso'}
            </Button>
          </div>
        </div>

        {/* Backend caído: se agotaron reintentos y polling */}
        <AnimatePresence>
          {isOffline && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              role="alert"
              className="mt-4 flex flex-col gap-3 rounded-xl border-2 border-ink-900 bg-ink-100 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex items-start gap-2.5">
                <CloudOff className="mt-0.5 h-4 w-4 shrink-0 text-ink-600" aria-hidden />
                <div>
                  <p className="text-[13px] font-bold text-ink-900">Backend offline</p>
                  <p className="text-[12px] text-ink-600">
                    No hay respuesta del servidor. Se detuvieron los reintentos para no consumir
                    recursos.
                  </p>
                </div>
              </div>
              <Button size="sm" variant="paper" onClick={retry} aria-label="Reintentar conexión">
                <RotateCw className="h-3.5 w-3.5" aria-hidden />
                Reintentar
              </Button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error de la última operación */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              role="alert"
              className="mt-4 rounded-xl border-2 border-clay-500 bg-clay-100 px-4 py-3"
            >
              <p className="text-[13px] font-medium text-clay-700">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Provenance */}
        {provenance.length > 0 && (
          <div className="mt-4">
            <ProvenanceBanner providers={provenance} isDemoSession={Boolean(user?.isDemo && isDemoData)} />
          </div>
        )}

        {(isRunning || isStarting) && (
          <div className="mt-4">
            <AnalysisTerminal active />
          </div>
        )}

        {/* ─── Cerebro ─── */}
        <div className="mt-6">
          <CerebroPanel state={cerebroState} session={session ?? null} />
        </div>

        {/* ─── Tabs ─── */}
        <div className="mt-6">
          {/* En móvil la fila scrollea en lugar de romperse */}
          <div
            role="tablist"
            aria-label="Secciones del análisis"
            className="flex items-center gap-1 overflow-x-auto rounded-lg border-2 border-ink-900 bg-paper p-1 shadow-hard-sm"
          >
            {tabs.map((t) => {
              const active = tab === t.id
              const badge = tabBadges[t.id]
              return (
                <button
                  key={t.id}
                  role="tab"
                  id={`tab-${t.id}`}
                  aria-selected={active}
                  aria-controls={`panel-${t.id}`}
                  tabIndex={active ? 0 : -1}
                  onClick={() => setTab(t.id)}
                  className={`relative flex shrink-0 items-center gap-1.5 rounded px-2.5 py-1.5 font-mono text-[10.5px] font-bold uppercase tracking-wider transition-colors sm:px-3 sm:text-[11px] ${
                    active ? 'text-white' : 'text-ink-500 hover:text-ink-900'
                  }`}
                >
                  {active && (
                    <motion.span
                      layoutId="analysis-tab-pill"
                      className="absolute inset-0 rounded bg-violet-600"
                      transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                    />
                  )}
                  <span className="relative">{t.label}</span>
                  {badge > 0 && (
                    <span
                      className={`relative ml-0.5 rounded-full px-1.5 py-0 font-mono text-[9px] font-bold ${
                        t.id === 'decisiones'
                          ? 'bg-clay-100 text-clay-700'
                          : 'bg-violet-100 text-violet-700'
                      }`}
                    >
                      {badge}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          <div className="mt-4">
            <AnimatePresence mode="wait">
              {tab === 'agentes' && (
                <motion.div
                  key="agentes"
                  role="tabpanel"
                  id="panel-agentes"
                  aria-labelledby="tab-agentes"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  {isStarting && !session ? (
                    <LoadingRegion label="Iniciando análisis">
                      <div className="grid gap-3 sm:grid-cols-2">
                        {Array.from({ length: 4 }, (_, i) => (
                          <CardSkeleton key={i} />
                        ))}
                      </div>
                    </LoadingRegion>
                  ) : session && session.agents.length > 0 ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {session.agents.map((ag, i) => (
                        <AgentCard key={ag.agent} agent={ag} index={i} />
                      ))}
                    </div>
                  ) : (
                    <AgentShowcaseCards />
                  )}

                  {/* Escenarios */}
                  {scenarios && scenarios.length > 0 && (
                    <div className="mt-4 overflow-hidden rounded-xl border-2 border-ink-200 bg-paper">
                      <button
                        onClick={() => setShowScenarios((v) => !v)}
                        aria-expanded={showScenarios}
                        aria-controls="risk-scenarios"
                        className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left"
                      >
                        <span className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-ink-700 sm:text-[11px]">
                          Escenarios de riesgo ({scenarios.length})
                        </span>
                        {showScenarios ? (
                          <ChevronUp className="h-4 w-4 shrink-0 text-ink-400" aria-hidden />
                        ) : (
                          <ChevronDown className="h-4 w-4 shrink-0 text-ink-400" aria-hidden />
                        )}
                      </button>
                      <AnimatePresence>
                        {showScenarios && (
                          <motion.div
                            id="risk-scenarios"
                            initial={{ height: 0 }}
                            animate={{ height: 'auto' }}
                            exit={{ height: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="space-y-2 border-t-2 border-ink-100 px-4 py-3">
                              {scenarios.map((sc, i) => {
                                const title = sc.title ?? sc.label ?? sc.kind ?? `Escenario ${i + 1}`
                                const prob =
                                  typeof sc.completion_probability === 'number'
                                    ? sc.completion_probability
                                    : typeof sc.probability === 'number'
                                      ? sc.probability
                                      : null
                                return (
                                  <div key={i} className="rounded-lg border-2 border-ink-100 p-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <p className="text-[13px] font-bold text-ink-900">{title}</p>
                                      {prob !== null && (
                                        <span className="font-mono text-[10px] text-ink-500">
                                          prob. {Math.round(prob * 100)}%
                                        </span>
                                      )}
                                    </div>
                                    {sc.description && (
                                      <p className="mt-0.5 text-[12px] text-ink-600">
                                        {sc.description}
                                      </p>
                                    )}
                                    <div className="mt-1.5 flex flex-wrap gap-2 font-mono text-[10px] text-ink-500">
                                      {sc.expected_cost != null && (
                                        <span className="rounded border border-ink-200 px-1.5 py-0.5">
                                          costo: {String(sc.expected_cost)}
                                        </span>
                                      )}
                                      {sc.expected_delay_days != null && (
                                        <span className="rounded border border-ink-200 px-1.5 py-0.5">
                                          +{sc.expected_delay_days}d
                                        </span>
                                      )}
                                      {sc.client_risk && (
                                        <span className="rounded border border-clay-300 px-1.5 py-0.5 text-clay-700">
                                          {sc.client_risk}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  {/* Pre-mortem: el backend lo manda como objeto, no como texto */}
                  {premortem && (
                    <div className="mt-3 rounded-xl border-2 border-dashed border-clay-300 bg-clay-100 p-4">
                      <p className="label-mono text-clay-700">Pre-mortem</p>
                      {premortem.assumed_failure && (
                        <p className="mt-1 text-[12.5px] leading-relaxed text-clay-700">
                          {premortem.assumed_failure}
                        </p>
                      )}
                      {[
                        { label: 'Modos de fallo', items: premortem.failure_modes },
                        { label: 'Señales tempranas', items: premortem.early_signals },
                        { label: 'Acciones preventivas', items: premortem.preventive_actions },
                      ].map(
                        (group) =>
                          group.items &&
                          group.items.length > 0 && (
                            <div key={group.label} className="mt-2.5">
                              <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-clay-600">
                                {group.label}
                              </p>
                              <ul className="mt-1 space-y-0.5">
                                {group.items.map((item, i) => (
                                  <li
                                    key={i}
                                    className="flex items-start gap-1.5 text-[12px] text-clay-700"
                                  >
                                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-clay-500" />
                                    <span>{item}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ),
                      )}
                    </div>
                  )}
                </motion.div>
              )}

              {tab === 'evidencias' && (
                <motion.div
                  key="evidencias"
                  role="tabpanel"
                  id="panel-evidencias"
                  aria-labelledby="tab-evidencias"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  <EvidenceList evidence={session?.evidence ?? []} />
                </motion.div>
              )}

              {tab === 'decisiones' && (
                <motion.div
                  key="decisiones"
                  role="tabpanel"
                  id="panel-decisiones"
                  aria-labelledby="tab-decisiones"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  <DecisionPanel
                    decisions={session?.decisions ?? []}
                    onApprove={onApprove}
                    onReject={onReject}
                  />
                </motion.div>
              )}

              {tab === 'timeline' && (
                <motion.div
                  key="timeline"
                  role="tabpanel"
                  id="panel-timeline"
                  aria-labelledby="tab-timeline"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  <TimelineView entries={session?.timeline ?? []} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Cadena causal */}
        {causalChain && causalChain.length > 0 && (
          <div className="mt-6 rounded-xl border-2 border-ink-200 bg-paper p-4">
            <p className="label-mono text-ink-500">Cadena causal</p>
            <ol className="mt-2 space-y-1.5">
              {causalChain.map((step, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="mt-0.5 shrink-0 font-mono text-[10px] font-bold text-violet-600">
                    {i + 1}.
                  </span>
                  <span className="text-[12.5px] text-ink-700">
                    {/* El backend manda objetos {cause, effect}; renderizar el
                        objeto directo tira el error #31 */}
                    {typeof step === 'string' ? (
                      step
                    ) : (
                      <>
                        <span className="font-medium">{step.cause}</span>
                        {step.effect && (
                          <>
                            {' → '}
                            <span>{step.effect}</span>
                          </>
                        )}
                      </>
                    )}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </AppShell>
  )
}
