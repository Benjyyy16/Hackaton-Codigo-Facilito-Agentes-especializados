import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  AlertCircle,
  Bot,
  GitBranch,
  Play,
  RotateCcw,
  Skull,
  Sparkles,
  Zap,
} from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { Button } from '@/components/ui/Button'
import { AgentDetail } from '@/components/datgent/AgentDetail'
import { CausalChain, PreMortemPanel, ScenariosPanel } from '@/components/datgent/RiskNarrative'
import { RiskScoreGauge } from '@/components/datgent/AgentPanels'
import {
  CerebroStatus,
  LiveAgentRow,
  LiveEvidenceFeed,
  LiveTimeline,
} from '@/components/datgent/LivePanels'
import { DecisionCard, ProvenanceBar } from '@/components/datgent/DecisionPanels'
import { ClaimsPanel, LiveEventFeed, SystemStatus } from '@/components/datgent/SystemPanels'
import { useDatgentEvents } from '@/hooks/useDatgentEvents'
import { LiveApiError, live } from '@/lib/liveApi'
import type { LiveSession, ProvenanceResponse } from '@/lib/liveApi'
import type { SchemaStatus } from '@/lib/datgentTypes'

/**
 * Cadencia del sondeo mientras el análisis corre.
 *
 * El WebSocket es la vía principal de actualización, pero el sondeo existe como red: si el
 * canal se cae a mitad del análisis, la interfaz sigue avanzando en lugar de congelarse en
 * el último evento recibido. Se detiene en cuanto la sesión termina.
 */
const POLL_INTERVAL_MS = 700

const ACTIVE_STATES = new Set([
  'starting_agents',
  'gathering_evidence',
  'consolidating',
  'generating_scenarios',
])

function Section({
  icon: Icon,
  title,
  subtitle,
  children,
  compact,
}: {
  icon: typeof Bot
  title: string
  subtitle?: string
  children: React.ReactNode
  compact?: boolean
}) {
  return (
    <section className={compact ? 'mt-6' : 'mt-10'}>
      <div className="flex items-center gap-2">
        <Icon className="h-5 w-5 text-violet-600" aria-hidden />
        <h2 className="font-display text-[24px] tracking-tightest text-ink-900">{title}</h2>
      </div>
      {subtitle && <p className="mt-1 text-[13px] text-ink-500">{subtitle}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

export default function RiskAnalysis() {
  const [params] = useSearchParams()
  /** Modo presentación: `?demo=true` arranca solo y simplifica la pantalla. */
  const presentationMode = params.get('demo') === 'true'

  const [session, setSession] = useState<LiveSession | null>(null)
  const [starting, setStarting] = useState(false)
  const [simulating, setSimulating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [provenance, setProvenance] = useState<ProvenanceResponse | null>(null)
  const [schema, setSchema] = useState<SchemaStatus | null>(null)

  const sessionIdRef = useRef<string | null>(null)
  const autoStartedRef = useRef(false)

  // Estado de conexión y eventos del canal en vivo.
  const { events: wsEvents, state: wsState } = useDatgentEvents()

  const handleSchemaStatus = useCallback((status: SchemaStatus) => setSchema(status), [])

  useEffect(() => {
    void live
      .provenance()
      .then(setProvenance)
      .catch(() => setProvenance(null))
  }, [])

  const refresh = useCallback(async () => {
    const id = sessionIdRef.current
    if (id === null) return
    try {
      setSession(await live.session(id))
    } catch {
      // Un sondeo fallido no se muestra: el siguiente lo reintenta y avisar de cada
      // hueco de red convertiría la pantalla en un muro de errores transitorios.
    }
  }, [])

  // Sondeo activo solo mientras la sesión avanza.
  useEffect(() => {
    if (session === null || !ACTIVE_STATES.has(session.state)) return
    const timer = window.setInterval(() => void refresh(), POLL_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [session, refresh])

  // El WebSocket es la vía rápida: cada evento del backend provoca una relectura
  // inmediata del estado, sin esperar al siguiente sondeo. Se usa el evento como
  // disparador y no como fuente de verdad porque el estado completo lo tiene el backend:
  // reconstruirlo a partir de eventos parciales abriría la puerta a que la interfaz y el
  // servidor divergieran si se pierde uno.
  const lastEventCount = useRef(0)
  useEffect(() => {
    if (wsEvents.length === lastEventCount.current) return
    lastEventCount.current = wsEvents.length
    if (sessionIdRef.current !== null) void refresh()
  }, [wsEvents, refresh])

  const start = useCallback(async () => {
    setStarting(true)
    setError(null)
    setSelectedAgent(null)
    try {
      const { session_id } = await live.start()
      sessionIdRef.current = session_id
      await refresh()
    } catch (caught) {
      if (caught instanceof LiveApiError && caught.status === 409) {
        // Ya hay un análisis en marcha: se limpia y se reintenta una vez, en lugar de
        // dejar al usuario ante un error que no puede resolver desde la interfaz.
        try {
          await live.reset()
          const { session_id } = await live.start()
          sessionIdRef.current = session_id
          await refresh()
        } catch {
          setError('Ya hay un análisis en curso y no se pudo reiniciar. Probá en unos segundos.')
        }
      } else {
        setError(caught instanceof LiveApiError ? caught.message : 'No se pudo iniciar el análisis.')
      }
    } finally {
      setStarting(false)
    }
  }, [refresh])

  // Modo presentación: arranca solo, una única vez.
  useEffect(() => {
    if (!presentationMode || autoStartedRef.current) return
    autoStartedRef.current = true
    void start()
  }, [presentationMode, start])

  async function simulateJira() {
    setSimulating(true)
    setError(null)
    try {
      const { session_id } = await live.simulateJira()
      sessionIdRef.current = session_id
      await refresh()
    } catch (caught) {
      setError(
        caught instanceof LiveApiError
          ? caught.message
          : 'No se pudo simular el evento de Jira.',
      )
    } finally {
      setSimulating(false)
    }
  }

  async function resetDemo() {
    try {
      await live.reset()
    } catch {
      // Reiniciar es idempotente desde el punto de vista del usuario: si el backend ya no
      // tenía sesiones, el resultado visible es el mismo.
    }
    sessionIdRef.current = null
    setSession(null)
    setSelectedAgent(null)
    setError(null)
    autoStartedRef.current = false
  }

  function onDecisionResolved() {
    // El estado completo de la decisión y la línea nueva de la cronología los escribe el
    // backend, así que se relee en lugar de adivinarlos aquí.
    void refresh()
  }

  const running = session !== null && ACTIVE_STATES.has(session.state)
  const busy = starting || running
  const riskCase = session?.risk_case ?? null
  const selected = riskCase?.agent_outputs.find((output) => output.agent === selectedAgent)
  const pendingDecisions = session?.decisions.filter((d) => d.approval_status === 'pending') ?? []

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-7xl px-5 py-9 sm:px-8 sm:py-12">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="label-mono text-ink-400">datgent cerebro</p>
            <h1
              className={
                presentationMode
                  ? 'mt-2 font-display text-[46px] leading-none tracking-tightest text-ink-900 sm:text-[60px]'
                  : 'mt-2 font-display text-[38px] leading-none tracking-tightest text-ink-900 sm:text-[46px]'
              }
            >
              Análisis en vivo
            </h1>
            <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-ink-600">
              Cuatro agentes investigan el mismo compromiso. El núcleo correlaciona sus
              hallazgos y propone acciones. Datgent recomienda; una persona decide.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button onClick={start} loading={busy} size="lg">
              <Play className="h-4 w-4" />
              Analizar compromiso
            </Button>
            {provenance?.demo_session && (
              <>
                <Button onClick={simulateJira} loading={simulating} variant="outline" size="lg">
                  <Zap className="h-4 w-4" />
                  Simular evento de Jira
                </Button>
                <button
                  type="button"
                  onClick={resetDemo}
                  className="inline-flex items-center gap-1.5 rounded-lg border-2 border-ink-900 bg-paper px-3 py-2 text-[12px] font-bold text-ink-900 transition hover:bg-ink-50"
                >
                  <RotateCcw className="h-3.5 w-3.5" aria-hidden />
                  Reiniciar demostración
                </button>
              </>
            )}
          </div>
        </header>

        {provenance && (
          <div className="mt-5">
            <div className="flex flex-wrap items-center gap-2">
              <ProvenanceBar
                providers={provenance.providers}
                demoSession={provenance.demo_session}
                persistence={session?.persistence ?? 'memory'}
              />
              <span
                className={
                  wsState === 'open'
                    ? 'rounded-full border-2 border-mint-500 bg-mint-50 px-2.5 py-1 font-mono text-[9px] font-bold uppercase tracking-wider text-mint-700'
                    : wsState === 'connecting'
                      ? 'rounded-full border-2 border-clay-500 bg-clay-100 px-2.5 py-1 font-mono text-[9px] font-bold uppercase tracking-wider text-clay-700'
                      : 'rounded-full border-2 border-ink-300 bg-ink-50 px-2.5 py-1 font-mono text-[9px] font-bold uppercase tracking-wider text-ink-500'
                }
                aria-live="polite"
              >
                {wsState === 'open'
                  ? 'en vivo'
                  : wsState === 'connecting'
                    ? 'reconectando'
                    : 'desconectado'}
              </span>
            </div>
          </div>
        )}

        {session?.persistence === 'memory' && (
          <p className="mt-3 rounded-lg border-2 border-clay-500 bg-clay-100 p-3 text-[12.5px] leading-snug text-clay-700">
            {session.persistence_note}
          </p>
        )}

        {error && (
          <p
            role="alert"
            className="mt-3 flex items-start gap-2 rounded-lg border-2 border-rose-500 bg-rose-50 p-3.5 text-[13px] leading-snug text-rose-700"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {error}
          </p>
        )}

        {/* Estado del núcleo y de los agentes: es la parte que se mueve. */}
        {session !== null && (
          <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_360px]">
            <div className="space-y-4">
              <CerebroStatus session={session} />
              <div className="space-y-2">
                {session.agents.map((agent) => (
                  <LiveAgentRow
                    key={agent.agent}
                    agent={agent}
                    selected={agent.agent === selectedAgent}
                    onSelect={() =>
                      setSelectedAgent(agent.agent === selectedAgent ? null : agent.agent)
                    }
                  />
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
                <h3 className="text-[15px] font-bold text-ink-900">
                  Evidencias ({session.evidence_count})
                </h3>
                <div className="mt-3 max-h-[320px] overflow-y-auto">
                  <LiveEvidenceFeed evidence={session.evidence} />
                </div>
              </div>
              {!presentationMode && <LiveEventFeed />}
            </div>
          </div>
        )}

        {session === null && !starting && (
          <div className="mt-8 rounded-xl border-2 border-dashed border-ink-300 bg-paper/60 p-10 text-center">
            <Sparkles className="mx-auto h-8 w-8 text-ink-300" aria-hidden />
            <p className="mt-3 text-[15px] font-bold text-ink-900">
              Pulsá «Analizar compromiso» para arrancar
            </p>
            <p className="mx-auto mt-1 max-w-md text-[13px] leading-relaxed text-ink-500">
              El caso es «Entregar integración de pagos empresariales antes del viernes»:
              penalización contractual, issue bloqueado sin responsable, checks fallidos,
              migración sin rollback y una tabla sin RLS.
            </p>
          </div>
        )}

        {selected && (
          <Section icon={Bot} title="Detalle del agente" compact>
            <AgentDetail output={selected} />
          </Section>
        )}

        {riskCase !== null && (
          <>
            <Section icon={Sparkles} title="Riesgo consolidado" compact>
              <RiskScoreGauge riskCase={riskCase} />
            </Section>

            {session !== null && session.timeline.length > 0 && (
              <Section
                icon={GitBranch}
                title="Cronología"
                subtitle="Cada línea es un evento real del análisis, no un guion."
              >
                <LiveTimeline events={session.timeline} />
              </Section>
            )}

            {pendingDecisions.length > 0 || (session?.decisions.length ?? 0) > 0 ? (
              <Section
                icon={Bot}
                title="Acciones que requieren aprobación"
                subtitle="Datgent recomienda. Una persona decide."
              >
                <div className="space-y-3">
                  {session?.decisions.map((decision) => (
                    <DecisionCard
                      key={decision.id}
                      decision={decision}
                      onResolved={onDecisionResolved}
                    />
                  ))}
                </div>
              </Section>
            ) : null}

            <Section
              icon={GitBranch}
              title="Cadena causal"
              subtitle="De la causa técnica al efecto en la fecha, y de ahí a la consecuencia económica."
            >
              <CausalChain steps={riskCase.causal_chain} />
            </Section>

            {riskCase.premortem && (
              <Section
                icon={Skull}
                title="Pre-mortem"
                subtitle="Se asume el fallo consumado y se trabaja hacia atrás."
              >
                <PreMortemPanel premortem={riskCase.premortem} />
              </Section>
            )}

            <Section
              icon={Sparkles}
              title="Escenarios de recuperación"
              subtitle="Los tres siempre, incluido no actuar: sin la línea base de la inacción, el coste de las otras dos no se puede juzgar."
            >
              <ScenariosPanel scenarios={riskCase.scenarios} />
            </Section>

            {!presentationMode && (
              <Section
                icon={AlertCircle}
                title="Qué se sabe y qué se supone"
                subtitle="Un plan que no distingue lo observado de lo supuesto no se puede auditar."
              >
                <ClaimsPanel riskCase={riskCase} />
              </Section>
            )}
          </>
        )}

        {!presentationMode && (
          <Section icon={Bot} title="Estado técnico">
            <div className="grid gap-4 lg:grid-cols-2">
              <SystemStatus onSchemaStatus={handleSchemaStatus} />
              <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
                <h3 className="text-[15px] font-bold text-ink-900">Enlaces técnicos</h3>
                <p className="mt-1 text-[12px] text-ink-500">
                  Para la demostración. La documentación no se incrusta en el producto.
                </p>
                <ul className="mt-3 space-y-1.5">
                  {[
                    { label: 'Swagger', path: '/docs' },
                    { label: 'Health', path: '/health' },
                    { label: 'Ready', path: '/ready' },
                    { label: 'Estado del esquema', path: '/admin/schema/status' },
                  ].map((link) => (
                    <li key={link.path}>
                      <a
                        href={`https://hackaton-codigo-facilito-agentes.onrender.com${link.path}`}
                        target="_blank"
                        rel="noreferrer"
                        className="font-mono text-[11.5px] text-violet-700 hover:underline"
                      >
                        {link.label} · {link.path}
                      </a>
                    </li>
                  ))}
                </ul>
                {schema && !schema.ready && (
                  <p className="mt-3 font-mono text-[10.5px] leading-snug text-clay-700">
                    faltan {schema.missing.length} de {schema.tables.length} tablas
                  </p>
                )}
              </div>
            </div>
          </Section>
        )}

        {session?.finished_at && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mt-10 text-center font-mono text-[10.5px] uppercase tracking-wider text-ink-400"
          >
            análisis terminado {new Date(session.finished_at).toLocaleString('es')} ·
            persistencia: {session.persistence}
          </motion.p>
        )}
      </div>
    </AppShell>
  )
}
