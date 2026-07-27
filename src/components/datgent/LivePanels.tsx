import { motion } from 'framer-motion'
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  CircleDashed,
  Clock,
  HelpCircle,
  Loader2,
  XCircle,
} from 'lucide-react'
import { AGENT_STATE_LABELS, CEREBRO_LABELS } from '@/lib/liveApi'
import type {
  CerebroState,
  LiveAgent,
  LiveAgentState,
  LiveEvidence,
  LiveSession,
  LiveTimelineEvent,
} from '@/lib/liveApi'
import { agentIcon, agentLabel, formatPercent } from '@/lib/datgentApi'
import { cn } from '@/lib/cn'

/**
 * Formatea la duración de un agente.
 *
 * Los agentes son funciones puras sin E/S, así que tardan menos de un milisegundo y el
 * reloj devuelve 0. Se muestra `<1 ms` en lugar de `0 ms` porque cero sugiere que no se
 * ejecutó, y en lugar de inflarlo con la pausa de presentación porque eso sería atribuir
 * al análisis un tiempo que no consumió.
 */
function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  if (ms === 0) return '<1 ms'
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

const AGENT_STATE_STYLES: Record<
  LiveAgentState,
  { box: string; badge: string; Icon: typeof CheckCircle2 }
> = {
  waiting: {
    box: 'border-ink-200 bg-ink-50',
    badge: 'border-ink-300 bg-paper text-ink-500',
    Icon: CircleDashed,
  },
  investigating: {
    box: 'border-violet-600 bg-violet-50',
    badge: 'border-violet-300 bg-violet-100 text-violet-700',
    Icon: Loader2,
  },
  completed: {
    box: 'border-ink-900 bg-paper',
    badge: 'border-mint-300 bg-mint-100 text-mint-700',
    Icon: CheckCircle2,
  },
  error: {
    box: 'border-rose-500 bg-rose-50',
    badge: 'border-rose-300 bg-rose-100 text-rose-700',
    Icon: XCircle,
  },
  insufficient_data: {
    box: 'border-dashed border-ink-300 bg-ink-50',
    badge: 'border-clay-300 bg-clay-100 text-clay-700',
    Icon: HelpCircle,
  },
}

export function LiveAgentRow({
  agent,
  onSelect,
  selected,
}: {
  agent: LiveAgent
  onSelect?: () => void
  selected?: boolean
}) {
  const style = AGENT_STATE_STYLES[agent.state]
  const { Icon } = style
  const clickable = agent.state === 'completed' || agent.state === 'insufficient_data'

  return (
    <button
      type="button"
      onClick={clickable ? onSelect : undefined}
      disabled={!clickable}
      aria-pressed={selected}
      className={cn(
        'flex w-full items-center gap-3 rounded-xl border-2 p-3.5 text-left shadow-hard-sm transition-all',
        style.box,
        clickable && 'hover:-translate-y-0.5',
        selected && 'ring-2 ring-violet-300',
      )}
    >
      <span className="text-xl" aria-hidden>
        {agentIcon(agent.agent)}
      </span>

      <span className="min-w-0 flex-1">
        <span className="block text-[13.5px] font-bold text-ink-900">
          {agentLabel(agent.agent)}
        </span>
        {agent.state === 'completed' && agent.risk_score !== null ? (
          <span className="block font-mono text-[10.5px] text-ink-500">
            riesgo {agent.risk_score}/100 · {agent.findings_count} hallazgo
            {agent.findings_count === 1 ? '' : 's'} · confianza{' '}
            {formatPercent(agent.confidence)}
          </span>
        ) : agent.state === 'insufficient_data' ? (
          <span className="block font-mono text-[10.5px] text-clay-700">
            no pudo evaluar: falta la señal de su proveedor
          </span>
        ) : agent.state === 'error' ? (
          <span className="block font-mono text-[10.5px] text-rose-600">
            {agent.error ?? 'el agente falló; el análisis continúa con el resto'}
          </span>
        ) : null}
      </span>

      <span
        className={cn(
          'inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[9.5px] font-bold uppercase tracking-wider',
          style.badge,
        )}
      >
        <Icon
          className={cn('h-3 w-3', agent.state === 'investigating' && 'animate-spin')}
          aria-hidden
        />
        {AGENT_STATE_LABELS[agent.state]}
      </span>

      {agent.duration_ms !== null && (
        <span className="shrink-0 font-mono text-[10.5px] tabular-nums text-ink-400">
          {formatDuration(agent.duration_ms)}
        </span>
      )}
    </button>
  )
}

const CEREBRO_ACTIVE: CerebroState[] = [
  'starting_agents',
  'gathering_evidence',
  'consolidating',
  'generating_scenarios',
]

export function CerebroStatus({ session }: { session: LiveSession }) {
  const active = CEREBRO_ACTIVE.includes(session.state)
  const failed = session.state === 'partial_error'

  return (
    <div
      className={cn(
        'rounded-xl border-2 p-5 shadow-hard',
        failed ? 'border-clay-500 bg-clay-100' : 'border-ink-900 bg-paper',
      )}
      aria-live="polite"
    >
      <div className="flex items-center gap-2.5">
        <Brain
          className={cn('h-5 w-5 text-violet-600', active && 'animate-pulse')}
          aria-hidden
        />
        <h3 className="text-[15px] font-bold text-ink-900">Datgent Cerebro</h3>
        <span
          className={cn(
            'ml-auto rounded-full border px-2.5 py-1 font-mono text-[9.5px] font-bold uppercase tracking-wider',
            failed
              ? 'border-clay-500 bg-paper text-clay-700'
              : session.state === 'completed' || session.state === 'awaiting_approval'
                ? 'border-mint-300 bg-mint-100 text-mint-700'
                : 'border-violet-300 bg-violet-50 text-violet-700',
          )}
        >
          {CEREBRO_LABELS[session.state]}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          {
            label: 'agentes',
            value: `${session.agents_completed}/${session.agents_total}`,
          },
          { label: 'evidencias', value: String(session.evidence_count) },
          {
            label: 'tiempo total',
            value: formatDuration(session.total_duration_ms),
          },
          {
            label: 'riesgo',
            value:
              session.risk_case === null
                ? '—'
                : `${session.risk_case.consolidated_score}/100`,
          },
        ].map((metric) => (
          <div key={metric.label}>
            <dt className="label-mono text-ink-400">{metric.label}</dt>
            <dd className="mt-0.5 font-display text-[22px] leading-none tracking-tightest text-ink-900">
              {metric.value}
            </dd>
          </div>
        ))}
      </dl>

      {session.risk_case !== null && (
        <p className="mt-3 font-mono text-[10.5px] text-ink-500">
          confianza global {formatPercent(session.risk_case.confidence)}
        </p>
      )}

      {failed && (
        <p className="mt-3 flex items-start gap-2 rounded-lg border-2 border-clay-500 bg-paper p-3 text-[12.5px] leading-snug text-clay-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Análisis parcial · {session.agents_completed} de {session.agents_total} agentes
            completados. El fallo de un agente no destruye el análisis: falta una dimensión
            del riesgo, y queda declarado.
          </span>
        </p>
      )}
    </div>
  )
}

export function LiveEvidenceFeed({ evidence }: { evidence: LiveEvidence[] }) {
  if (evidence.length === 0) {
    return (
      <p className="text-[12.5px] text-ink-500">
        Las evidencias aparecen a medida que cada agente termina su investigación.
      </p>
    )
  }

  return (
    <ul className="space-y-2">
      {evidence.map((item, index) => (
        <motion.li
          key={`${item.provider}-${item.external_id}-${index}`}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="rounded-xl border-2 border-ink-200 bg-paper p-3"
        >
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="rounded border border-ink-300 bg-ink-50 px-1.5 py-0.5 font-mono text-[9.5px] font-bold uppercase text-ink-700">
              {item.provider}
            </span>
            {item.external_id && (
              <span className="font-mono text-[10.5px] font-medium text-ink-900">
                {item.external_id}
              </span>
            )}
            {/* La procedencia va junto al dato y no en una leyenda aparte: un dato
                simulado que se lee sin su etiqueta se recuerda como real. */}
            <span
              className={cn(
                'rounded-full border px-1.5 py-0.5 font-mono text-[8.5px] font-bold uppercase',
                item.provenance === 'real'
                  ? 'border-mint-300 bg-mint-100 text-mint-700'
                  : 'border-clay-300 bg-clay-100 text-clay-700',
              )}
            >
              {item.provenance === 'real' ? 'real' : 'demo'}
            </span>
            <span className="ml-auto font-mono text-[9.5px] text-ink-400">
              {new Date(item.observed_at).toLocaleTimeString('es')}
            </span>
          </div>

          {item.field && (
            <p className="mt-1 font-mono text-[10.5px] text-ink-600">
              {item.field}
              {item.value !== null && <span className="text-ink-900"> = {item.value}</span>}
            </p>
          )}
          <p className="mt-1 text-[12px] leading-snug text-ink-700">{item.explanation}</p>
        </motion.li>
      ))}
    </ul>
  )
}

export function LiveTimeline({ events }: { events: LiveTimelineEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="text-[12.5px] text-ink-500">
        La cronología se llena con los eventos reales del análisis.
      </p>
    )
  }

  return (
    <ol className="space-y-1.5">
      {events.map((event, index) => (
        <motion.li
          key={`${event.at}-${index}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-start gap-3 rounded-lg border border-ink-200 bg-paper px-3 py-2"
        >
          <span className="shrink-0 font-mono text-[10.5px] tabular-nums text-ink-400">
            {new Date(event.at).toLocaleTimeString('es', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            })}
          </span>
          <span
            className={cn(
              'shrink-0 rounded border px-1.5 py-0.5 font-mono text-[8.5px] font-bold uppercase',
              event.actor_type === 'human'
                ? 'border-violet-300 bg-violet-50 text-violet-700'
                : 'border-ink-200 bg-ink-50 text-ink-500',
            )}
          >
            {event.actor_name}
          </span>
          <span className="min-w-0 flex-1 text-[12px] leading-snug text-ink-800">
            {event.summary}
          </span>
          {event.reference && (
            <span className="shrink-0 font-mono text-[9.5px] text-ink-400">
              {event.reference}
            </span>
          )}
        </motion.li>
      ))}
    </ol>
  )
}

export { Clock }
