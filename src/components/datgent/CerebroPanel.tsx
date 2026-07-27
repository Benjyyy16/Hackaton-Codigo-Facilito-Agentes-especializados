import { motion, AnimatePresence } from 'framer-motion'
import { Brain, CheckCircle, AlertTriangle, Loader2, Clock } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { CerebroState, LiveSession } from '@/store/analysisTypes'

interface CerebroPanelProps {
  state: CerebroState
  session: LiveSession | null
}

const stateLabels: Record<CerebroState, string> = {
  ready: 'Listo para analizar',
  starting_agents: 'Iniciando agentes…',
  gathering_evidence: 'Recopilando evidencia…',
  consolidating: 'Consolidando resultados…',
  generating_scenarios: 'Generando escenarios…',
  awaiting_approval: 'Esperando aprobación humana',
  completed: 'Análisis completado',
  partial_error: 'Completado con errores parciales',
}

const stateColors: Record<CerebroState, string> = {
  ready: 'border-ink-300 bg-paper',
  starting_agents: 'border-violet-400 bg-violet-50',
  gathering_evidence: 'border-violet-500 bg-violet-50',
  consolidating: 'border-violet-600 bg-violet-100',
  generating_scenarios: 'border-violet-600 bg-violet-100',
  awaiting_approval: 'border-clay-500 bg-clay-50',
  completed: 'border-mint-500 bg-mint-50',
  partial_error: 'border-clay-500 bg-clay-50',
}

const isActive = (s: CerebroState) =>
  ['starting_agents', 'gathering_evidence', 'consolidating', 'generating_scenarios'].includes(s)

function RiskGauge({ score, severity }: { score: number; severity: string }) {
  const color =
    score >= 75 ? 'bg-clay-500' : score >= 50 ? 'bg-clay-400' : score >= 25 ? 'bg-violet-500' : 'bg-mint-500'
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="label-mono text-ink-500">riesgo consolidado</span>
        <span
          className={cn(
            'font-mono text-[11px] font-bold uppercase tracking-wider',
            score >= 75 ? 'text-clay-700' : score >= 50 ? 'text-clay-600' : 'text-ink-700',
          )}
        >
          {severity} · {score}/100
        </span>
      </div>
      <div className="flex h-3 gap-[2px] overflow-hidden rounded border-2 border-ink-900 bg-paper p-[2px]">
        <motion.div
          className={cn('rounded-sm', color)}
          initial={{ width: '0%' }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  )
}

export function CerebroPanel({ state, session }: CerebroPanelProps) {
  const active = isActive(state)
  const rc = session?.risk_case

  return (
    <motion.div
      layout
      className={cn(
        'overflow-hidden rounded-xl border-2 shadow-hard transition-colors duration-500',
        stateColors[state],
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-3 border-b-2 border-ink-100 px-4 py-3">
        <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border-2 border-ink-900 bg-paper">
          {active ? (
            <Loader2 className="h-4 w-4 animate-spin text-violet-600" />
          ) : state === 'completed' ? (
            <CheckCircle className="h-4 w-4 text-mint-600" />
          ) : state === 'partial_error' || state === 'awaiting_approval' ? (
            <AlertTriangle className="h-4 w-4 text-clay-600" />
          ) : (
            <Brain className="h-4 w-4 text-ink-500" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] font-bold uppercase tracking-widest text-ink-400">
            Datgent Cerebro
          </p>
          <AnimatePresence mode="wait">
            <motion.p
              key={state}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              className="text-[14px] font-semibold text-ink-900"
            >
              {stateLabels[state]}
            </motion.p>
          </AnimatePresence>
        </div>
        {session && (
          <div className="shrink-0 text-right">
            <p className="label-mono text-ink-400">agentes</p>
            <p className="font-display text-[20px] font-bold leading-none text-ink-900">
              {session.agents_completed}/{session.agents_total}
            </p>
          </div>
        )}
      </div>

      {/* Métricas */}
      <AnimatePresence>
        {session && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="space-y-3 px-4 py-3">
              {/* Riesgo */}
              {rc && <RiskGauge score={rc.consolidated_score} severity={rc.severity} />}

              {/* Stats fila */}
              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-lg border-2 border-ink-100 p-2 text-center">
                  <p className="label-mono text-ink-400">evidencias</p>
                  <p className="font-display text-[18px] font-bold text-ink-900">
                    {session.evidence_count}
                  </p>
                </div>
                <div className="rounded-lg border-2 border-ink-100 p-2 text-center">
                  <p className="label-mono text-ink-400">decisiones</p>
                  <p className="font-display text-[18px] font-bold text-ink-900">
                    {session.decisions.length}
                  </p>
                </div>
                <div className="rounded-lg border-2 border-ink-100 p-2 text-center">
                  <p className="label-mono text-ink-400">confianza</p>
                  <p className="font-display text-[18px] font-bold text-ink-900">
                    {rc ? Math.round(rc.confidence * 100) + '%' : '—'}
                  </p>
                </div>
              </div>

              {/* Tiempo */}
              {session.total_duration_ms > 0 && (
                <div className="flex items-center gap-1.5 text-ink-400">
                  <Clock className="h-3 w-3" />
                  <span className="font-mono text-[10px]">
                    {(session.total_duration_ms / 1000).toFixed(1)}s total
                  </span>
                </div>
              )}

              {/* Resumen */}
              {rc?.summary && (
                <p className="rounded-lg border-2 border-dashed border-ink-200 bg-paper/70 px-3 py-2 text-[12.5px] leading-relaxed text-ink-700">
                  {rc.summary}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
