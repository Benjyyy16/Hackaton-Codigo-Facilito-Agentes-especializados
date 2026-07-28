import { motion } from 'framer-motion'
import { CheckCircle, AlertTriangle, Loader2, Clock, Database, Code, DollarSign, Ticket } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { LiveAgentRecord } from '@/store/analysisTypes'

interface AgentCardProps {
  agent: LiveAgentRecord
  index: number
  onViewEvidence?: () => void
}

const agentMeta: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  'Jira Agent': { label: 'Jira', icon: Ticket, color: 'text-blue-600' },
  'Code Agent': { label: 'Código', icon: Code, color: 'text-violet-600' },
  'Finance Agent': { label: 'Finanzas', icon: DollarSign, color: 'text-mint-600' },
  'Database Agent': { label: 'Supabase', icon: Database, color: 'text-emerald-600' },
}

function getAgentMeta(name: string) {
  // Búsqueda exacta primero, luego por substring
  if (agentMeta[name]) return agentMeta[name]
  for (const [key, val] of Object.entries(agentMeta)) {
    if (name.toLowerCase().includes(key.split(' ')[0].toLowerCase())) return val
  }
  return { label: name, icon: Database, color: 'text-ink-600' }
}

const stateLabel: Record<string, string> = {
  waiting: 'Esperando',
  investigating: 'Investigando…',
  completed: 'Completado',
  error: 'Error',
  insufficient_data: 'Datos insuficientes',
}

const severityColor: Record<string, string> = {
  critical: 'text-red-700 bg-red-50 border-red-300',
  high: 'text-clay-700 bg-clay-100 border-clay-400',
  medium: 'text-clay-600 bg-clay-50 border-clay-300',
  low: 'text-mint-700 bg-mint-50 border-mint-400',
}

export function AgentCard({ agent, index, onViewEvidence }: AgentCardProps) {
  const meta = getAgentMeta(agent.agent)
  const Icon = meta.icon
  const isWaiting = agent.state === 'waiting'
  const isInvestigating = agent.state === 'investigating'
  const isDone = agent.state === 'completed'
  const isError = agent.state === 'error'
  const isInsufficient = agent.state === 'insufficient_data'

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className={cn(
        'overflow-hidden rounded-xl border-2 shadow-hard-sm transition-colors duration-300',
        isWaiting && 'border-ink-200 bg-paper/60 opacity-60',
        isInvestigating && 'border-violet-400 bg-violet-50',
        isDone && 'border-ink-900 bg-paper',
        isError && 'border-clay-500 bg-clay-50',
        isInsufficient && 'border-ink-300 bg-paper',
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2.5 px-3.5 py-2.5">
        <span
          className={cn(
            'grid h-7 w-7 shrink-0 place-items-center rounded-lg border-2 border-ink-900',
            isWaiting ? 'bg-ink-100' : 'bg-paper',
          )}
        >
          <Icon className={cn('h-3.5 w-3.5', isWaiting ? 'text-ink-400' : meta.color)} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-bold text-ink-900">{meta.label}</p>
          <p className={cn('label-mono', isInvestigating ? 'text-violet-600' : 'text-ink-400')}>
            {stateLabel[agent.state] ?? agent.state}
          </p>
        </div>
        <div className="shrink-0">
          {isWaiting && <span className="h-4 w-4 rounded-full border-2 border-ink-200 bg-ink-100 inline-block" />}
          {isInvestigating && <Loader2 className="h-4 w-4 animate-spin text-violet-500" />}
          {isDone && <CheckCircle className="h-4 w-4 text-mint-500" />}
          {isError && <AlertTriangle className="h-4 w-4 text-clay-600" />}
          {isInsufficient && <AlertTriangle className="h-4 w-4 text-ink-400" />}
        </div>
      </div>

      {/* Resultados */}
      {(isDone || isInsufficient) && (
        <div className="space-y-2 border-t-2 border-ink-100 px-3.5 py-2.5">
          {/* Riesgo */}
          <div className="flex items-center justify-between">
            <span className="label-mono text-ink-400">riesgo</span>
            <span
              className={cn(
                'rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase',
                severityColor[agent.severity] ?? 'text-ink-700 bg-ink-50 border-ink-200',
              )}
            >
              {agent.severity} · {agent.risk_score}/100
            </span>
          </div>

          {/* Confianza + hallazgos */}
          <div className="flex items-center gap-3">
            <span className="label-mono text-ink-400">
              confianza {Math.round(agent.confidence * 100)}%
            </span>
            <span className="label-mono text-ink-400">
              {agent.findings_count} hallazgo{agent.findings_count !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Barra riesgo */}
          <div className="flex h-2 gap-[2px] overflow-hidden rounded border border-ink-200 bg-paper p-[2px]">
            <motion.div
              className={cn(
                'rounded-sm',
                agent.risk_score >= 75 ? 'bg-clay-500' : agent.risk_score >= 50 ? 'bg-clay-400' : 'bg-violet-500',
              )}
              initial={{ width: '0%' }}
              animate={{ width: `${agent.risk_score}%` }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            />
          </div>

          {/* Duración */}
          {agent.duration_ms > 0 && (
            <div className="flex items-center gap-1 text-ink-400">
              <Clock className="h-2.5 w-2.5" />
              <span className="font-mono text-[10px]">{agent.duration_ms}ms</span>
            </div>
          )}

          {/* Datos insuficientes */}
          {isInsufficient && agent.missing_information.length > 0 && (
            <div className="space-y-0.5">
              <p className="label-mono text-clay-600">información faltante</p>
              {agent.missing_information.slice(0, 2).map((m, i) => (
                <p key={i} className="font-mono text-[10px] text-ink-500">
                  · {m}
                </p>
              ))}
            </div>
          )}

          {onViewEvidence && agent.findings_count > 0 && (
            <button
              type="button"
              onClick={onViewEvidence}
              className="pt-1 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-700"
            >
              Ver evidencia →
            </button>
          )}
        </div>
      )}
    </motion.div>
  )
}
