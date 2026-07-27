import { memo, useId, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle, XCircle, User } from 'lucide-react'
import { cn } from '@/lib/cn'
import { Button } from '@/components/ui/Button'
import type { LiveDecision } from '@/store/analysisTypes'

interface DecisionPanelProps {
  decisions: LiveDecision[]
  onApprove: (id: string, by: string) => Promise<void>
  onReject: (id: string, by: string, reason: string) => Promise<void>
}

interface DecisionCardProps {
  decision: LiveDecision
  onApprove: (id: string, by: string) => Promise<void>
  onReject: (id: string, by: string, reason: string) => Promise<void>
}

/** Memoizada: aprobar una decisión no re-renderiza las demás tarjetas. */
const DecisionCard = memo(function DecisionCard({
  decision,
  onApprove,
  onReject,
}: DecisionCardProps) {
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<'idle' | 'reject'>('idle')
  const [reason, setReason] = useState('')
  const reasonId = useId()

  const isPending = decision.approval_status === 'pending'
  const isApproved = decision.approval_status === 'approved'
  const isRejected = decision.approval_status === 'rejected'

  async function handleApprove() {
    setLoading(true)
    try {
      await onApprove(decision.id, 'Operador Datgent')
    } finally {
      setLoading(false)
    }
  }

  async function handleReject() {
    if (!reason.trim()) return
    setLoading(true)
    try {
      await onReject(decision.id, 'Operador Datgent', reason.trim())
      setMode('idle')
      setReason('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'overflow-hidden rounded-xl border-2 transition-colors',
        isPending && 'border-clay-400 bg-clay-50',
        isApproved && 'border-mint-400 bg-mint-50',
        isRejected && 'border-ink-200 bg-ink-50 opacity-75',
      )}
    >
      {/* Cabecera */}
      <div className="flex items-start gap-3 px-4 py-3">
        <div
          className={cn(
            'mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full border-2',
            isPending ? 'border-clay-500 bg-paper' : isApproved ? 'border-mint-500 bg-mint-100' : 'border-ink-300 bg-paper',
          )}
        >
          {isApproved ? (
            <CheckCircle className="h-3.5 w-3.5 text-mint-600" />
          ) : isRejected ? (
            <XCircle className="h-3.5 w-3.5 text-ink-500" />
          ) : (
            <User className="h-3 w-3 text-clay-600" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[13.5px] font-bold text-ink-900">{decision.title}</p>
            <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
              {decision.action_type}
            </span>
          </div>
          <p className="mt-1 text-[12px] leading-relaxed text-ink-600">{decision.rationale}</p>
          <p className="mt-1 label-mono text-ink-400">agente: {decision.agent}</p>
        </div>
        {/* Badge estado */}
        <span
          className={cn(
            'shrink-0 rounded border px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase',
            isPending && 'border-clay-400 bg-clay-100 text-clay-700',
            isApproved && 'border-mint-500 bg-mint-100 text-mint-700',
            isRejected && 'border-ink-300 bg-ink-100 text-ink-600',
          )}
        >
          {decision.approval_status}
        </span>
      </div>

      {/* Acciones */}
      <AnimatePresence>
        {isPending && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="border-t-2 border-clay-200 px-4 py-3">
              {/* Aviso: persona decide */}
              <p className="mb-2.5 font-mono text-[10px] font-bold uppercase tracking-wider text-clay-600">
                Datgent recomienda · Una persona decide
              </p>

              {mode === 'idle' ? (
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="mint"
                    loading={loading}
                    onClick={handleApprove}
                    aria-label={`Aprobar: ${decision.title}`}
                  >
                    <CheckCircle className="h-3.5 w-3.5" aria-hidden />
                    Aprobar
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setMode('reject')}
                    disabled={loading}
                    aria-label={`Rechazar: ${decision.title}`}
                  >
                    <XCircle className="h-3.5 w-3.5" aria-hidden />
                    Rechazar
                  </Button>
                </div>
              ) : (
                <div className="space-y-2">
                  <label htmlFor={reasonId} className="label-mono block text-ink-500">
                    Motivo del rechazo
                  </label>
                  <textarea
                    id={reasonId}
                    className="w-full rounded-lg border-2 border-ink-300 bg-paper px-3 py-2 font-sans text-[12.5px] text-ink-900 placeholder-ink-400 focus:border-ink-700 focus:outline-none"
                    rows={2}
                    placeholder="Motivo del rechazo…"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="ink"
                      loading={loading}
                      disabled={!reason.trim()}
                      onClick={handleReject}
                    >
                      Confirmar rechazo
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setMode('idle')
                        setReason('')
                      }}
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Resultado */}
      {(isApproved || isRejected) && decision.approved_by && (
        <div className="border-t-2 border-ink-100 px-4 py-2">
          <p className="font-mono text-[10.5px] text-ink-500">
            {isApproved ? '✓ Aprobado' : '✗ Rechazado'} por{' '}
            <span className="font-bold text-ink-700">{decision.approved_by}</span>
            {decision.approved_at && (
              <> · {new Date(decision.approved_at).toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' })}</>
            )}
          </p>
          {isRejected && decision.rejection_reason && (
            <p className="mt-0.5 font-mono text-[10.5px] text-ink-500">
              Motivo: {decision.rejection_reason}
            </p>
          )}
        </div>
      )}
    </motion.div>
  )
})

export function DecisionPanel({ decisions, onApprove, onReject }: DecisionPanelProps) {
  if (decisions.length === 0) {
    return (
      <p className="rounded-xl border-2 border-dashed border-ink-200 py-6 text-center font-mono text-[10.5px] uppercase tracking-wider text-ink-300">
        Sin decisiones pendientes
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <AnimatePresence initial={false}>
        {decisions.map((d) => (
          <DecisionCard
            key={d.id}
            decision={d}
            onApprove={onApprove}
            onReject={onReject}
          />
        ))}
      </AnimatePresence>
    </div>
  )
}
