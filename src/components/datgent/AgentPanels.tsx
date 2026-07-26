import { motion } from 'framer-motion'
import { AlertTriangle, HelpCircle } from 'lucide-react'
import {
  SEVERITY_CLASSES,
  SEVERITY_LABELS,
  agentIcon,
  agentLabel,
  formatPercent,
} from '@/lib/datgentApi'
import type { AgentOutput, RiskCase } from '@/lib/datgentTypes'
import { cn } from '@/lib/cn'

/** Barras del medidor. Segmentado y no continuo, coherente con el resto del sistema. */
const GAUGE_SEGMENTS = 20

export function RiskScoreGauge({ riskCase }: { riskCase: RiskCase }) {
  const filled = Math.round((riskCase.consolidated_score / 100) * GAUGE_SEGMENTS)
  const severityClass = SEVERITY_CLASSES[riskCase.severity]

  return (
    <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-mono text-ink-400">riesgo consolidado</p>
          <p className="mt-1 font-display text-[54px] leading-none tracking-tightest text-ink-900">
            {riskCase.consolidated_score}
            <span className="text-[24px] text-ink-300">/100</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span
            className={cn(
              'rounded-full border-2 px-3 py-1 font-mono text-[11px] font-bold uppercase tracking-wider',
              severityClass,
            )}
          >
            {SEVERITY_LABELS[riskCase.severity]}
          </span>
          <span className="font-mono text-[11px] text-ink-500">
            confianza {formatPercent(riskCase.confidence)}
          </span>
        </div>
      </div>

      <div
        className="mt-4 flex h-4 gap-[2px] rounded border-2 border-ink-900 bg-paper p-[2px]"
        role="meter"
        aria-valuenow={riskCase.consolidated_score}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Riesgo consolidado ${riskCase.consolidated_score} de 100`}
      >
        {Array.from({ length: GAUGE_SEGMENTS }, (_, index) => (
          <motion.span
            key={index}
            className={cn(
              'flex-1 rounded-[1px]',
              index < filled ? severityClass.split(' ')[0].replace('border', 'bg') : 'bg-ink-100',
            )}
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ delay: index * 0.015 }}
          />
        ))}
      </div>

      <p className="mt-4 text-[14px] leading-relaxed text-ink-700">{riskCase.summary}</p>

      {riskCase.is_partial && (
        <p className="mt-3 flex items-start gap-2 rounded-lg border-2 border-clay-500 bg-clay-100 p-3 text-[12.5px] text-clay-700">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Análisis parcial: algún agente no pudo ejecutarse, así que falta una dimensión
            del riesgo. El resultado sigue siendo utilizable, pero no está completo.
          </span>
        </p>
      )}
    </div>
  )
}

export function AgentOutputCard({
  output,
  selected,
  onSelect,
}: {
  output: AgentOutput
  selected: boolean
  onSelect: () => void
}) {
  // Un agente que no pudo concluir se muestra apagado y con el hueco declarado. La
  // diferencia entre "no encontré riesgo" y "no pude mirar" es la información más fácil de
  // perder en una interfaz, y la que más cambia una decisión.
  const skipped = output.status === 'skipped'

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        'flex w-full flex-col rounded-xl border-2 p-4 text-left shadow-hard-sm transition-all',
        skipped
          ? 'border-dashed border-ink-300 bg-ink-50'
          : 'border-ink-900 bg-paper hover:-translate-y-0.5',
        selected && 'ring-2 ring-violet-300',
        selected && !skipped && 'border-violet-600',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={cn('text-xl', skipped && 'opacity-40')} aria-hidden>
          {agentIcon(output.agent)}
        </span>
        {skipped ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-ink-300 bg-paper px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-ink-500">
            <HelpCircle className="h-3 w-3" aria-hidden />
            sin datos
          </span>
        ) : (
          <span
            className={cn(
              'rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase',
              SEVERITY_CLASSES[output.severity],
            )}
          >
            {SEVERITY_LABELS[output.severity]}
          </span>
        )}
      </div>

      <h3
        className={cn(
          'mt-2 text-[14px] font-bold',
          skipped ? 'text-ink-500' : 'text-ink-900',
        )}
      >
        {agentLabel(output.agent)}
      </h3>

      {skipped ? (
        <p className="mt-1 text-[11px] leading-tight text-ink-500">
          No pudo evaluar: falta la señal de su proveedor.
        </p>
      ) : (
        <>
          <p className="mt-1 font-display text-[26px] leading-none text-ink-900">
            {output.risk_score}
            <span className="text-[13px] text-ink-300">/100</span>
          </p>
          <p className="mt-1.5 font-mono text-[10px] text-ink-500">
            {output.findings.length} hallazgo{output.findings.length === 1 ? '' : 's'} ·
            confianza {formatPercent(output.confidence)}
          </p>
        </>
      )}

      {output.missing_information.length > 0 && (
        <p className="mt-2 border-t border-dashed border-ink-200 pt-2 text-[10.5px] leading-tight text-clay-700">
          {output.missing_information.length} hueco
          {output.missing_information.length === 1 ? '' : 's'} de información
        </p>
      )}
    </button>
  )
}
