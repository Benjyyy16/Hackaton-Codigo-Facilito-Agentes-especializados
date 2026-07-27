import { AnimatePresence, motion } from 'framer-motion'
import { cn } from '@/lib/cn'
import type { Evidence } from '@/store/analysisTypes'

interface EvidenceListProps {
  evidence: Evidence[]
}

const providerColor: Record<string, string> = {
  jira: 'border-blue-300 bg-blue-50 text-blue-700',
  github: 'border-violet-300 bg-violet-50 text-violet-700',
  rightway: 'border-mint-400 bg-mint-50 text-mint-700',
  supabase: 'border-emerald-300 bg-emerald-50 text-emerald-700',
}

function ProvLabel({ provenance }: { provenance: 'real' | 'demo' }) {
  return (
    <span
      className={cn(
        'shrink-0 rounded border px-1 py-0.5 font-mono text-[8.5px] font-bold uppercase tracking-wider',
        provenance === 'real'
          ? 'border-mint-400 bg-mint-50 text-mint-700'
          : 'border-clay-300 bg-clay-50 text-clay-600',
      )}
    >
      {provenance === 'real' ? 'real' : 'demo'}
    </span>
  )
}

export function EvidenceList({ evidence }: EvidenceListProps) {
  if (evidence.length === 0) {
    return (
      <p className="rounded-xl border-2 border-dashed border-ink-200 py-6 text-center font-mono text-[10.5px] uppercase tracking-wider text-ink-300">
        Sin evidencias aún
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <AnimatePresence initial={false}>
        {evidence.slice().reverse().map((ev, i) => {
          const pColor = providerColor[ev.provider] ?? 'border-ink-200 bg-ink-50 text-ink-600'
          return (
            <motion.div
              key={`${ev.provider}-${ev.field}-${i}`}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.2 }}
              className="rounded-lg border-2 border-ink-100 bg-paper p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      'rounded border px-1.5 py-0.5 font-mono text-[9.5px] font-bold uppercase',
                      pColor,
                    )}
                  >
                    {ev.provider}
                  </span>
                  {ev.external_id && (
                    <span className="font-mono text-[10.5px] font-semibold text-ink-700">
                      {ev.external_id}
                    </span>
                  )}
                  <ProvLabel provenance={ev.provenance} />
                </div>
                <span className="font-mono text-[9px] text-ink-400">
                  {new Date(ev.observed_at).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>

              <p className="mt-1.5 text-[12px] font-semibold text-ink-900">{ev.field}</p>
              <p className="mt-0.5 font-mono text-[11px] text-ink-600">{ev.value}</p>
              {ev.explanation && (
                <p className="mt-1 text-[11.5px] leading-relaxed text-ink-500">{ev.explanation}</p>
              )}
              <p className="mt-1 label-mono text-ink-400">{ev.agent}</p>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
