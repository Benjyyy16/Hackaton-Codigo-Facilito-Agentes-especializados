import { useState } from 'react'
import { motion } from 'framer-motion'
import { CheckCircle2, Loader2, ShieldCheck, XCircle } from 'lucide-react'
import { LiveApiError, live } from '@/lib/liveApi'
import type { LiveDecision, ProviderProvenance } from '@/lib/liveApi'
import { agentLabel } from '@/lib/datgentApi'
import { cn } from '@/lib/cn'

/** Quién aprueba en la demostración. En producción vendría de la sesión autenticada. */
const DEMO_APPROVER = 'Usuario Hackathon'

/**
 * Acciones que tocan un sistema externo. Se listan aparte porque piden una segunda
 * confirmación: aprobar es una decisión, y ejecutar algo irreversible en Jira o en la base
 * de datos es otra. Juntarlas convertiría un clic en un cambio en producción.
 */
const SENSITIVE_ACTIONS = new Set([
  'execute_sql',
  'merge_pull_request',
  'create_pull_request',
  'send_external_communication',
  'post_accounting_entry',
  'block_deployment',
])

export function DecisionCard({
  decision,
  onResolved,
}: {
  decision: LiveDecision
  /** Se llama tras aceptar la operación para que quien manda relea el estado. */
  onResolved: () => void
}) {
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  const pending = decision.approval_status === 'pending'
  const sensitive = SENSITIVE_ACTIONS.has(decision.action_type)

  async function approve() {
    // Segunda confirmación para lo que toca sistemas externos.
    if (sensitive && !confirming) {
      setConfirming(true)
      return
    }
    setBusy('approve')
    setError(null)
    try {
      await live.approve(decision.id, DEMO_APPROVER)
      onResolved()
    } catch (caught) {
      setError(caught instanceof LiveApiError ? caught.message : 'No se pudo aprobar.')
    } finally {
      setBusy(null)
      setConfirming(false)
    }
  }

  async function reject() {
    setBusy('reject')
    setError(null)
    try {
      await live.reject(decision.id, DEMO_APPROVER, 'Rechazada durante la demostración.')
      onResolved()
    } catch (caught) {
      setError(caught instanceof LiveApiError ? caught.message : 'No se pudo rechazar.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <motion.article
      layout
      className={cn(
        'rounded-xl border-2 p-4 shadow-hard-sm',
        decision.approval_status === 'approved'
          ? 'border-mint-500 bg-mint-50'
          : decision.approval_status === 'rejected'
            ? 'border-ink-300 bg-ink-50'
            : 'border-ink-900 bg-paper',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <code className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-ink-700">
              {decision.action_type}
            </code>
            <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
              {agentLabel(decision.agent)}
            </span>
            {sensitive && (
              <span className="rounded-full border border-clay-500 bg-clay-100 px-2 py-0.5 font-mono text-[8.5px] font-bold uppercase text-clay-700">
                acción sensible
              </span>
            )}
          </div>
          <h4 className="mt-1.5 text-[13.5px] font-bold leading-snug text-ink-900">
            {decision.title}
          </h4>
          <p className="mt-1 text-[12px] leading-snug text-ink-600">{decision.rationale}</p>
        </div>
        {pending && (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-full border-2 border-violet-600 bg-violet-50 px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-violet-700">
            <ShieldCheck className="h-3 w-3" aria-hidden />
            requiere aprobación
          </span>
        )}
      </div>

      {decision.approval_status === 'approved' && (
        <div className="mt-3 rounded-lg border-2 border-mint-500 bg-paper p-3">
          <p className="flex items-center gap-1.5 text-[12.5px] font-bold text-mint-700">
            <CheckCircle2 className="h-4 w-4" aria-hidden />
            Decisión aprobada
          </p>
          <dl className="mt-2 space-y-1 font-mono text-[10.5px]">
            <div className="flex gap-2">
              <dt className="text-ink-400">aprobada por</dt>
              <dd className="text-ink-900">{decision.approved_by}</dd>
            </div>
            {decision.approved_at && (
              <div className="flex gap-2">
                <dt className="text-ink-400">cuándo</dt>
                <dd className="text-ink-900">
                  {new Date(decision.approved_at).toLocaleString('es')}
                </dd>
              </div>
            )}
            <div className="flex gap-2">
              <dt className="text-ink-400">estado</dt>
              <dd className="text-clay-700">
                {decision.execution_status === 'not_started'
                  ? 'pendiente de ejecución'
                  : decision.execution_status}
              </dd>
            </div>
          </dl>
          <p className="mt-2 text-[11px] leading-snug text-ink-500">
            La acción queda registrada y aprobada, pero no se ejecuta: no hay ejecutor
            asociado, así que nada cambia en Jira ni en la base de datos.
          </p>
        </div>
      )}

      {decision.approval_status === 'rejected' && (
        <p className="mt-3 flex items-center gap-1.5 rounded-lg border border-ink-300 bg-paper p-2.5 text-[12px] text-ink-600">
          <XCircle className="h-4 w-4 shrink-0 text-ink-400" aria-hidden />
          Rechazada por {decision.approved_by ?? DEMO_APPROVER}
          {decision.rejection_reason && ` · ${decision.rejection_reason}`}
        </p>
      )}

      {error && (
        <p role="alert" className="mt-2 text-[11.5px] font-medium text-rose-600">
          {error}
        </p>
      )}

      {pending && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={approve}
            disabled={busy !== null}
            aria-label={
              confirming
                ? `Confirmar acción sensible: ${decision.title}`
                : `Aprobar: ${decision.title}`
            }
            className={cn(
              'inline-flex items-center gap-1.5 rounded-lg border-2 border-ink-900 px-3 py-1.5 text-[11.5px] font-bold transition disabled:opacity-50',
              confirming
                ? 'bg-clay-500 text-ink-900'
                : 'bg-violet-600 text-white hover:bg-violet-700',
            )}
          >
            {busy === 'approve' && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
            {confirming ? 'Confirmar: es una acción sensible' : 'Aprobar'}
          </button>
          <button
            type="button"
            onClick={reject}
            disabled={busy !== null}
            aria-label={`Rechazar: ${decision.title}`}
            className="rounded-lg border-2 border-ink-900 bg-paper px-3 py-1.5 text-[11.5px] font-bold text-ink-900 transition hover:bg-ink-50 disabled:opacity-50"
          >
            Rechazar
          </button>
          {confirming && (
            <button
              type="button"
              onClick={() => setConfirming(false)}
              aria-label={`Cancelar la confirmación de: ${decision.title}`}
              className="text-[11.5px] font-medium text-ink-500 underline"
            >
              cancelar
            </button>
          )}
        </div>
      )}
    </motion.article>
  )
}

export function ProvenanceBar({
  providers,
  demoSession,
  persistence,
}: {
  providers: ProviderProvenance[]
  demoSession: boolean
  persistence: 'supabase' | 'memory'
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {demoSession && (
        <span className="rounded-full border-2 border-clay-500 bg-clay-100 px-3 py-1 font-mono text-[9.5px] font-bold uppercase tracking-wider text-clay-700">
          sesión demo · datos simulados
        </span>
      )}
      {providers.map((provider) => (
        <span
          key={provider.provider}
          className={cn(
            'rounded-full border px-2.5 py-1 font-mono text-[9px] font-bold uppercase tracking-wider',
            provider.provenance === 'real'
              ? 'border-mint-500 bg-mint-50 text-mint-700'
              : 'border-ink-200 bg-ink-50 text-ink-500',
          )}
        >
          {provider.label}
        </span>
      ))}
      <span
        className={cn(
          'rounded-full border px-2.5 py-1 font-mono text-[9px] font-bold uppercase tracking-wider',
          persistence === 'supabase'
            ? 'border-mint-500 bg-mint-50 text-mint-700'
            : 'border-clay-500 bg-clay-100 text-clay-700',
        )}
      >
        {persistence === 'supabase' ? 'persistido en supabase' : 'sin persistir · en memoria'}
      </span>
    </div>
  )
}
