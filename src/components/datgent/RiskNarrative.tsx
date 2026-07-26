import { motion } from 'framer-motion'
import { ArrowDown, Skull, TrendingDown, Users, Handshake } from 'lucide-react'
import { formatMoney, formatPercent } from '@/lib/datgentApi'
import type { CausalStep, PreMortem, Scenario, ScenarioKind } from '@/lib/datgentTypes'
import { cn } from '@/lib/cn'

/** Texto para un campo que el backend dejó nulo. */
const NO_ESTIMATE = 'sin datos para estimar'

export function CausalChain({ steps }: { steps: CausalStep[] }) {
  if (steps.length === 0) {
    return (
      <p className="text-[13px] text-ink-500">
        No se pudo construir una cadena causal: hacen falta hallazgos en más de una
        dimensión para encadenar causa y efecto.
      </p>
    )
  }

  return (
    <ol className="space-y-0">
      {steps.map((step, index) => (
        <li key={step.step}>
          <motion.div
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.08 }}
            className="rounded-xl border-2 border-ink-900 bg-paper p-4 shadow-hard-sm"
          >
            <div className="flex items-start gap-3">
              <span
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 border-ink-900 bg-violet-600 font-mono text-[11px] font-bold text-white"
                aria-hidden
              >
                {step.step}
              </span>
              <div className="min-w-0 flex-1">
                <p className="label-mono text-ink-400">causa</p>
                <p className="text-[13px] font-medium leading-snug text-ink-900">
                  {step.cause}
                </p>
                <p className="label-mono mt-2 text-mint-700">efecto</p>
                <p className="text-[13px] leading-snug text-ink-700">{step.effect}</p>
              </div>
              {step.confidence < 1 && (
                <span className="shrink-0 rounded-full border border-violet-300 bg-violet-50 px-2 py-0.5 font-mono text-[9px] font-bold text-violet-700">
                  {formatPercent(step.confidence)}
                </span>
              )}
            </div>
          </motion.div>
          {index < steps.length - 1 && (
            <div className="flex justify-center py-1.5" aria-hidden>
              <ArrowDown className="h-4 w-4 text-ink-300" />
            </div>
          )}
        </li>
      ))}
    </ol>
  )
}

export function PreMortemPanel({ premortem }: { premortem: PreMortem }) {
  const blocks: Array<{ title: string; items: string[]; tone: string }> = [
    { title: 'Modos de fallo', items: premortem.failure_modes, tone: 'text-rose-700' },
    { title: 'Señales tempranas', items: premortem.early_signals, tone: 'text-clay-700' },
    { title: 'Acciones preventivas', items: premortem.preventive_actions, tone: 'text-mint-700' },
  ]

  return (
    <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
      <div className="flex items-start gap-3 rounded-lg border-2 border-rose-500 bg-rose-50 p-3.5">
        <Skull className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" aria-hidden />
        <div>
          <p className="label-mono text-rose-700">se asume el fallo</p>
          <p className="mt-1 text-[13.5px] font-medium leading-snug text-ink-900">
            {premortem.assumed_failure}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-3">
        {blocks.map((block) => (
          <div key={block.title}>
            <p className={cn('label-mono mb-2', block.tone)}>{block.title}</p>
            <ul className="space-y-1.5">
              {block.items.map((item, index) => (
                <li key={index} className="text-[12px] leading-snug text-ink-700">
                  · {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  )
}

const SCENARIO_META: Record<ScenarioKind, { icon: typeof TrendingDown; tone: string }> = {
  do_nothing: { icon: TrendingDown, tone: 'border-rose-500 bg-rose-50' },
  add_capacity: { icon: Users, tone: 'border-clay-500 bg-clay-100' },
  renegotiate_scope: { icon: Handshake, tone: 'border-mint-500 bg-mint-50' },
}

function Metric({ label, value }: { label: string; value: string | null }) {
  const missing = value === null
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-dashed border-ink-200 py-1.5 last:border-0">
      <span className="label-mono text-ink-400">{label}</span>
      <span
        className={cn(
          'text-right font-mono text-[11.5px]',
          // Un campo nulo se muestra como "sin datos" y nunca como 0: presentar una
          // ausencia de estimación como un cero convertiría un hueco en una afirmación.
          missing ? 'italic text-ink-400' : 'font-bold text-ink-900',
        )}
      >
        {missing ? NO_ESTIMATE : value}
      </span>
    </div>
  )
}

export function ScenariosPanel({ scenarios }: { scenarios: Scenario[] }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {scenarios.map((scenario, index) => {
        const meta = SCENARIO_META[scenario.kind]
        const Icon = meta.icon
        return (
          <motion.article
            key={scenario.kind}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.08 }}
            className="flex flex-col rounded-xl border-2 border-ink-900 bg-paper shadow-hard"
          >
            <header
              className={cn('flex items-center gap-2 border-b-2 border-ink-900 p-3.5', meta.tone)}
            >
              <Icon className="h-4 w-4 shrink-0 text-ink-900" aria-hidden />
              <h3 className="text-[14px] font-bold text-ink-900">{scenario.title}</h3>
            </header>

            <div className="flex flex-1 flex-col p-4">
              <p className="text-[12.5px] leading-relaxed text-ink-700">
                {scenario.description}
              </p>

              <div className="mt-3">
                <Metric
                  label="coste esperado"
                  value={formatMoney(scenario.expected_cost)}
                />
                <Metric
                  label="exposición residual"
                  value={formatMoney(scenario.residual_exposure)}
                />
                <Metric
                  label="prob. de cumplir"
                  value={formatPercent(scenario.completion_probability)}
                />
                <Metric
                  label="retraso esperado"
                  value={
                    scenario.expected_delay_days === null
                      ? null
                      : `${scenario.expected_delay_days} día(s)`
                  }
                />
              </div>

              {scenario.client_risk && (
                <div className="mt-3">
                  <p className="label-mono text-ink-400">riesgo de cliente</p>
                  <p className="text-[12px] leading-snug text-ink-700">
                    {scenario.client_risk}
                  </p>
                </div>
              )}

              {scenario.technical_impact && (
                <div className="mt-2.5">
                  <p className="label-mono text-ink-400">impacto técnico</p>
                  <p className="text-[12px] leading-snug text-ink-700">
                    {scenario.technical_impact}
                  </p>
                </div>
              )}

              {scenario.new_scope && (
                <div className="mt-2.5">
                  <p className="label-mono text-ink-400">alcance nuevo</p>
                  <p className="text-[12px] leading-snug text-ink-700">{scenario.new_scope}</p>
                </div>
              )}
            </div>
          </motion.article>
        )
      })}
    </div>
  )
}
