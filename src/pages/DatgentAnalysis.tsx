import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Play, Zap, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { Button } from '@/components/ui/Button'
import { WsIndicator } from '@/components/datgent/WsIndicator'
import { CerebroPanel } from '@/components/datgent/CerebroPanel'
import { AgentCard } from '@/components/datgent/AgentCard'
import { EvidenceList } from '@/components/datgent/EvidenceList'
import { DecisionPanel } from '@/components/datgent/DecisionPanel'
import { TimelineView } from '@/components/datgent/TimelineView'
import { ProvenanceBanner } from '@/components/datgent/ProvenanceBanner'
import { useAnalysis } from '@/hooks/useAnalysis'
import { useWsEvents } from '@/hooks/useWsEvents'
import type { WsEvent } from '@/store/analysisTypes'

type Tab = 'agentes' | 'evidencias' | 'decisiones' | 'timeline'

const tabs: { id: Tab; label: string }[] = [
  { id: 'agentes', label: 'Agentes' },
  { id: 'evidencias', label: 'Evidencias' },
  { id: 'decisiones', label: 'Decisiones' },
  { id: 'timeline', label: 'Timeline' },
]

export default function DatgentAnalysis() {
  const [tab, setTab] = useState<Tab>('agentes')
  const [showScenarios, setShowScenarios] = useState(false)
  const [searchParams] = useSearchParams()

  const analysis = useAnalysis()

  // Auto-iniciar análisis si hay repo en query param
  useEffect(() => {
    const repo = searchParams.get('repo')
    const sessionParam = searchParams.get('session')
    if (repo && !analysis.sessionId && !sessionParam && !analysis.isRunning) {
      // Iniciar análisis de ese repo
      analysis.startAnalysis().catch(() => {
        // Error manejado por useAnalysis
      })
    }
  }, [searchParams, analysis.sessionId, analysis.isRunning, analysis.startAnalysis])

  // Conectar WS solo cuando hay sesión o análisis en curso
  const onWsEvent = useCallback(
    (e: WsEvent) => analysis.handleWsEvent(e),
    [analysis.handleWsEvent],
  )
  const { wsState } = useWsEvents({
    onEvent: onWsEvent,
    sessionId: analysis.sessionId,
    enabled: true,
  })

  // Sincronizar wsState al store
  useEffect(() => {
    analysis.setWsState(wsState)
  }, [wsState, analysis.setWsState])

  // Cargar provenance al montar
  useEffect(() => {
    analysis.loadProvenance()
  }, [analysis.loadProvenance])

  // Cambiar a tab evidencias cuando lleguen evidencias
  useEffect(() => {
    if (analysis.session && analysis.session.evidence_count > 0 && tab === 'agentes') {
      // no cambiar tab automáticamente — el usuario elige
    }
  }, [analysis.session?.evidence_count])

  // Cambiar a decisiones al llegar awaiting_approval
  useEffect(() => {
    if (analysis.session?.state === 'awaiting_approval') {
      setTab('decisiones')
    }
  }, [analysis.session?.state])

  const session = analysis.session
  const cerebroState = session?.state ?? 'ready'
  const isRunning = analysis.isRunning

  // Contadores para badges
  const pendingDecisions = session?.decisions.filter((d) => d.approval_status === 'pending').length ?? 0
  const evidenceCount = session?.evidence_count ?? 0

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-5 py-7 sm:px-8">
        {/* ─── Encabezado ─── */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="grid h-9 w-9 place-items-center rounded-lg border-2 border-ink-900 bg-paper shadow-hard-sm">
                <Brain className="h-4.5 w-4.5 text-violet-600" />
              </div>
              <h1 className="font-display text-[32px] leading-none tracking-tightest text-ink-900 sm:text-[38px]">
                Datgent
              </h1>
            </div>
            <p className="mt-1.5 text-[13px] text-ink-500">
              Análisis multiagente de compromisos en riesgo
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <WsIndicator state={wsState} />

            {/* Simular Jira */}
            {!isRunning && (
              <Button
                size="sm"
                variant="outline"
                onClick={analysis.simulateJira}
                title="Simula un evento Jira crítico (solo demo)"
              >
                <Zap className="h-3.5 w-3.5" />
                Simular Jira
              </Button>
            )}

            {/* Reset */}
            {session && !isRunning && (
              <Button size="sm" variant="ghost" onClick={analysis.reset}>
                <RefreshCw className="h-3.5 w-3.5" />
                Limpiar
              </Button>
            )}

            {/* Analizar */}
            <Button
              size="sm"
              variant="primary"
              loading={isRunning}
              disabled={isRunning}
              onClick={analysis.startAnalysis}
            >
              <Play className="h-3.5 w-3.5" />
              {isRunning ? 'Analizando…' : 'Analizar compromiso'}
            </Button>
          </div>
        </div>

        {/* Error */}
        <AnimatePresence>
          {analysis.error && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="mt-4 rounded-xl border-2 border-clay-500 bg-clay-50 px-4 py-3"
            >
              <p className="text-[13px] font-medium text-clay-700">{analysis.error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Provenance */}
        {analysis.provenance.length > 0 && (
          <div className="mt-4">
            <ProvenanceBanner
              providers={analysis.provenance}
              isDemoSession={analysis.provenance.some((p) => p.provenance === 'demo')}
            />
          </div>
        )}

        {/* ─── Cerebro ─── */}
        <div className="mt-6">
          <CerebroPanel state={cerebroState} session={session ?? null} />
        </div>

        {/* ─── Tabs ─── */}
        <div className="mt-6">
          <div className="flex items-center gap-1 rounded-lg border-2 border-ink-900 bg-paper p-1 shadow-hard-sm">
            {tabs.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                aria-pressed={tab === t.id}
                className={`relative flex items-center gap-1.5 rounded px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider transition-colors ${
                  tab === t.id ? 'text-white' : 'text-ink-500 hover:text-ink-900'
                }`}
              >
                {tab === t.id && (
                  <motion.span
                    layoutId="analysis-tab-pill"
                    className="absolute inset-0 rounded bg-violet-600"
                    transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                  />
                )}
                <span className="relative">{t.label}</span>
                {/* badges */}
                {t.id === 'evidencias' && evidenceCount > 0 && (
                  <span className="relative ml-0.5 rounded-full bg-violet-100 px-1.5 py-0 font-mono text-[9px] font-bold text-violet-700">
                    {evidenceCount}
                  </span>
                )}
                {t.id === 'decisiones' && pendingDecisions > 0 && (
                  <span className="relative ml-0.5 rounded-full bg-clay-100 px-1.5 py-0 font-mono text-[9px] font-bold text-clay-700">
                    {pendingDecisions}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="mt-4">
            <AnimatePresence mode="wait">
              {tab === 'agentes' && (
                <motion.div
                  key="agentes"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  {session && session.agents.length > 0 ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {session.agents.map((ag, i) => (
                        <AgentCard key={ag.agent} agent={ag} index={i} />
                      ))}
                    </div>
                  ) : (
                    <p className="rounded-xl border-2 border-dashed border-ink-200 py-10 text-center font-mono text-[10.5px] uppercase tracking-wider text-ink-300">
                      Inicia un análisis para ver los agentes
                    </p>
                  )}

                  {/* Escenarios */}
                  {session?.risk_case?.scenarios && session.risk_case.scenarios.length > 0 && (
                    <div className="mt-4 overflow-hidden rounded-xl border-2 border-ink-200 bg-paper">
                      <button
                        onClick={() => setShowScenarios((v) => !v)}
                        className="flex w-full items-center justify-between px-4 py-2.5 text-left"
                      >
                        <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-ink-700">
                          Escenarios de riesgo ({session.risk_case.scenarios.length})
                        </span>
                        {showScenarios ? (
                          <ChevronUp className="h-4 w-4 text-ink-400" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-ink-400" />
                        )}
                      </button>
                      <AnimatePresence>
                        {showScenarios && (
                          <motion.div
                            initial={{ height: 0 }}
                            animate={{ height: 'auto' }}
                            exit={{ height: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="space-y-2 border-t-2 border-ink-100 px-4 py-3">
                              {session.risk_case.scenarios.map((sc, i) => (
                                <div
                                  key={i}
                                  className="rounded-lg border-2 border-ink-100 p-3"
                                >
                                  <div className="flex items-center justify-between">
                                    <p className="text-[13px] font-bold text-ink-900">{sc.label}</p>
                                    <span className="font-mono text-[10px] text-ink-500">
                                      P:{Math.round(sc.probability * 100)}% I:{sc.impact}/100
                                    </span>
                                  </div>
                                  <p className="mt-0.5 text-[12px] text-ink-600">{sc.description}</p>
                                </div>
                              ))}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )}

                  {/* Pre-mortem */}
                  {session?.risk_case?.premortem && (
                    <div className="mt-3 rounded-xl border-2 border-dashed border-clay-300 bg-clay-50 p-4">
                      <p className="label-mono text-clay-600">Pre-mortem</p>
                      <p className="mt-1 text-[12.5px] leading-relaxed text-clay-800">
                        {session.risk_case.premortem}
                      </p>
                    </div>
                  )}
                </motion.div>
              )}

              {tab === 'evidencias' && (
                <motion.div
                  key="evidencias"
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
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                >
                  <DecisionPanel
                    decisions={session?.decisions ?? []}
                    onApprove={analysis.approveDecision}
                    onReject={analysis.rejectDecision}
                  />
                </motion.div>
              )}

              {tab === 'timeline' && (
                <motion.div
                  key="timeline"
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
        {session?.risk_case?.causal_chain && session.risk_case.causal_chain.length > 0 && (
          <div className="mt-6 rounded-xl border-2 border-ink-200 bg-paper p-4">
            <p className="label-mono text-ink-500">Cadena causal</p>
            <ol className="mt-2 space-y-1">
              {session.risk_case.causal_chain.map((step, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="mt-0.5 shrink-0 font-mono text-[10px] font-bold text-violet-600">
                    {i + 1}.
                  </span>
                  <span className="text-[12.5px] text-ink-700">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </AppShell>
  )
}
