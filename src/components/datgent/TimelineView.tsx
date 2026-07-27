import { AnimatePresence, motion } from 'framer-motion'
import { Bot, User, Cpu } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { TimelineEntry } from '@/store/analysisTypes'

interface TimelineViewProps {
  entries: TimelineEntry[]
}

const actorIcon: Record<string, React.ElementType> = {
  agent: Bot,
  human: User,
  system: Cpu,
}

const eventColor: Record<string, string> = {
  'analysis.started': 'bg-violet-500',
  'analysis.completed': 'bg-mint-500',
  'agent_run.started': 'bg-violet-400',
  'agent_run.completed': 'bg-violet-600',
  'agent_run.error': 'bg-clay-500',
  'decision.approved': 'bg-mint-500',
  'decision.rejected': 'bg-clay-500',
}

function dot(type: string) {
  return eventColor[type] ?? 'bg-ink-400'
}

export function TimelineView({ entries }: TimelineViewProps) {
  if (entries.length === 0) {
    return (
      <p className="rounded-xl border-2 border-dashed border-ink-200 py-6 text-center font-mono text-[10.5px] uppercase tracking-wider text-ink-300">
        Timeline vacío
      </p>
    )
  }

  return (
    <div className="relative space-y-0">
      {/* línea vertical */}
      <div className="absolute left-[15px] top-2 bottom-2 w-[2px] bg-ink-100" />

      <AnimatePresence initial={false}>
        {entries.map((entry, i) => {
          const Icon = actorIcon[entry.actor_type] ?? Cpu
          return (
            <motion.div
              key={entry.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25, delay: i === entries.length - 1 ? 0 : 0 }}
              className="relative flex items-start gap-3 pb-3 pl-[32px]"
            >
              {/* dot */}
              <span
                className={cn(
                  'absolute left-[8px] top-1.5 h-3.5 w-3.5 shrink-0 rounded-full border-2 border-paper',
                  dot(entry.event_type),
                )}
              />

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="flex items-center gap-1 font-mono text-[10px] font-semibold text-ink-700">
                    <Icon className="h-2.5 w-2.5" />
                    {entry.actor_name}
                  </span>
                  <span className="font-mono text-[9px] uppercase tracking-wider text-ink-400">
                    {entry.event_type}
                  </span>
                  <span className="ml-auto font-mono text-[9px] text-ink-400">
                    {new Date(entry.at).toLocaleTimeString('es', {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </span>
                </div>
                <p className="mt-0.5 text-[12px] text-ink-600">{entry.summary}</p>
              </div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
