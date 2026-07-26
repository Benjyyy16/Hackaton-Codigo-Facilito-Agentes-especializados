import { useCallback, useState } from 'react'
import { motion } from 'framer-motion'
import { AlertCircle, Bot, GitBranch, Play, Skull, Sparkles } from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { Button } from '@/components/ui/Button'
import { AgentOutputCard, RiskScoreGauge } from '@/components/datgent/AgentPanels'
import { AgentDetail } from '@/components/datgent/AgentDetail'
import {
  CausalChain,
  PreMortemPanel,
  ScenariosPanel,
} from '@/components/datgent/RiskNarrative'
import {
  ClaimsPanel,
  LiveEventFeed,
  PersistenceNotice,
  ProposedActions,
  SystemStatus,
} from '@/components/datgent/SystemPanels'
import { DatgentApiError, DatgentNetworkError, datgent } from '@/lib/datgentApi'
import type { OrchestrateResponse, SchemaStatus } from '@/lib/datgentTypes'

function Section({
  icon: Icon,
  title,
  subtitle,
  children,
}: {
  icon: typeof Bot
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  return (
    <section className="mt-10">
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
  const [result, setResult] = useState<OrchestrateResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [schema, setSchema] = useState<SchemaStatus | null>(null)

  const handleSchemaStatus = useCallback((status: SchemaStatus) => setSchema(status), [])

  async function runDemo() {
    setLoading(true)
    setError(null)
    try {
      const response = await datgent.orchestrateDemo()
      setResult(response)
      // Se abre el detalle del agente que domina la puntuación: es lo que alguien querría
      // ver primero, y evita que el usuario tenga que buscarlo.
      const worst = response.agent_outputs.reduce(
        (best, current) => (current.risk_score > best.risk_score ? current : best),
        response.agent_outputs[0],
      )
      setSelectedAgent(worst?.agent ?? null)
    } catch (caught) {
      if (caught instanceof DatgentApiError || caught instanceof DatgentNetworkError) {
        setError(caught.message)
      } else {
        setError('Error inesperado al ejecutar el análisis.')
      }
    } finally {
      setLoading(false)
    }
  }

  const selected = result?.agent_outputs.find((output) => output.agent === selectedAgent)

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-7xl px-5 py-9 sm:px-8 sm:py-12">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="label-mono text-ink-400">datgent cerebro</p>
            <h1 className="mt-2 font-display text-[38px] leading-none tracking-tightest text-ink-900 sm:text-[46px]">
              Análisis de riesgo
            </h1>
            <p className="mt-2 max-w-2xl text-[14px] leading-relaxed text-ink-600">
              Cuatro agentes especializados analizan el mismo compromiso. El núcleo
              correlaciona sus hallazgos, construye la cadena causal y propone escenarios de
              recuperación.
            </p>
          </div>
          <Button onClick={runDemo} loading={loading} size="lg">
            <Play className="h-4 w-4" />
            Analizar caso demo
          </Button>
        </header>

        <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_340px]">
          <div className="space-y-4">
            <PersistenceNotice schema={schema} />
            {error && (
              <p
                role="alert"
                className="flex items-start gap-2 rounded-lg border-2 border-rose-500 bg-rose-50 p-3.5 text-[13px] leading-snug text-rose-700"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                {error}
              </p>
            )}
            {result && <RiskScoreGauge riskCase={result.risk_case} />}
          </div>
          <div className="space-y-4">
            <SystemStatus onSchemaStatus={handleSchemaStatus} />
            <LiveEventFeed />
          </div>
        </div>

        {!result && !loading && (
          <div className="mt-10 rounded-xl border-2 border-dashed border-ink-300 bg-paper/60 p-10 text-center">
            <Sparkles className="mx-auto h-8 w-8 text-ink-300" aria-hidden />
            <p className="mt-3 text-[15px] font-bold text-ink-900">
              Todavía no ejecutaste ningún análisis
            </p>
            <p className="mx-auto mt-1 max-w-md text-[13px] leading-relaxed text-ink-500">
              El caso de demostración es «Entregar integración de pagos empresariales antes
              del viernes»: penalización contractual, issue bloqueado sin responsable, pull
              request con checks fallidos, migración sin rollback y una tabla sin RLS.
            </p>
          </div>
        )}

        {result && (
          <>
            <Section
              icon={Bot}
              title="Agentes"
              subtitle="Un agente sin señal de su proveedor no dice «no hay riesgo»: dice «no pude mirar». Se muestra apagado."
            >
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {result.agent_outputs.map((output) => (
                  <AgentOutputCard
                    key={output.agent}
                    output={output}
                    selected={output.agent === selectedAgent}
                    onSelect={() =>
                      setSelectedAgent(
                        output.agent === selectedAgent ? null : output.agent,
                      )
                    }
                  />
                ))}
              </div>
              {selected && (
                <div className="mt-4">
                  <AgentDetail output={selected} />
                </div>
              )}
            </Section>

            <Section
              icon={GitBranch}
              title="Cadena causal"
              subtitle="De la causa técnica al efecto en la fecha, y de ahí a la consecuencia económica."
            >
              <CausalChain steps={result.risk_case.causal_chain} />
            </Section>

            {result.risk_case.premortem && (
              <Section
                icon={Skull}
                title="Pre-mortem"
                subtitle="Se asume el fallo consumado y se trabaja hacia atrás: produce modos de fallo concretos en lugar de preocupaciones genéricas."
              >
                <PreMortemPanel premortem={result.risk_case.premortem} />
              </Section>
            )}

            <Section
              icon={Sparkles}
              title="Escenarios de recuperación"
              subtitle="Los tres siempre, incluido no actuar: sin la línea base de la inacción, el coste de las otras dos no se puede juzgar."
            >
              <ScenariosPanel scenarios={result.risk_case.scenarios} />
            </Section>

            <Section
              icon={AlertCircle}
              title="Qué se sabe y qué se supone"
              subtitle="Un plan que no distingue lo observado de lo supuesto no se puede auditar."
            >
              <ClaimsPanel riskCase={result.risk_case} />
            </Section>

            <Section
              icon={Bot}
              title="Acciones propuestas"
              subtitle="El sistema propone; una persona decide. Ninguna se ejecuta sola."
            >
              <ProposedActions
                actions={result.proposed_actions}
                persistenceReady={schema?.ready ?? false}
              />
            </Section>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-10 text-center font-mono text-[10.5px] uppercase tracking-wider text-ink-400"
            >
              análisis ejecutado {new Date(result.analyzed_at).toLocaleString('es')} ·
              persistido: {result.persisted ? 'sí' : 'no'}
            </motion.p>
          </>
        )}
      </div>
    </AppShell>
  )
}
