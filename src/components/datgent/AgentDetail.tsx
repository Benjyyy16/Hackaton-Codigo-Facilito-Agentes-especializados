import { motion } from 'framer-motion'
import { ExternalLink, Zap } from 'lucide-react'
import { SEVERITY_CLASSES, SEVERITY_LABELS, agentLabel, formatPercent } from '@/lib/datgentApi'
import type { AgentOutput, Evidence, Finding } from '@/lib/datgentTypes'
import { cn } from '@/lib/cn'

/** Etiqueta legible del origen de una evidencia. */
const SOURCE_LABELS: Record<Evidence['source_type'], string> = {
  jira: 'Jira',
  github: 'GitHub',
  finance: 'Finanzas',
  supabase: 'Supabase',
  document: 'Documento',
  computed: 'Derivado',
}

function EvidenceRow({ evidence }: { evidence: Evidence }) {
  return (
    <li className="rounded-lg border border-ink-200 bg-paper p-2.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="rounded border border-ink-300 bg-ink-50 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase text-ink-600">
          {SOURCE_LABELS[evidence.source_type]}
        </span>
        {evidence.external_id && (
          <span className="font-mono text-[10px] font-medium text-ink-700">
            {evidence.external_id}
          </span>
        )}
        {evidence.field && (
          <span className="font-mono text-[10px] text-ink-500">
            {evidence.field}
            {evidence.value !== null && (
              <span className="text-ink-900"> = {evidence.value}</span>
            )}
          </span>
        )}
        {evidence.source_url && (
          <a
            href={evidence.source_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-[10px] font-bold text-violet-700 hover:underline"
            aria-label={`Abrir ${evidence.external_id ?? 'el origen'} en una pestaña nueva`}
          >
            ver origen
            <ExternalLink className="h-3 w-3" aria-hidden />
          </a>
        )}
      </div>
      <p className="mt-1.5 text-[11.5px] leading-snug text-ink-600">{evidence.explanation}</p>
    </li>
  )
}

function FindingCard({ finding }: { finding: Finding }) {
  // La confianza por debajo de 1 significa que el hallazgo es una inferencia, no un dato
  // observado. Se marca para que quien lea sepa cuánto peso darle.
  const inferred = finding.confidence < 1

  return (
    <div className="rounded-xl border-2 border-ink-200 bg-paper p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <code className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-ink-700">
              {finding.code}
            </code>
            <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
              {finding.category}
            </span>
            {inferred && (
              <span className="rounded-full border border-violet-300 bg-violet-50 px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-violet-700">
                inferencia · {formatPercent(finding.confidence)}
              </span>
            )}
          </div>
          <p className="mt-1.5 text-[13.5px] font-medium leading-snug text-ink-900">
            {finding.summary}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              'rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase',
              SEVERITY_CLASSES[finding.severity],
            )}
          >
            {SEVERITY_LABELS[finding.severity]}
          </span>
          <span className="font-display text-[20px] leading-none text-ink-900">
            {finding.risk_score}
          </span>
        </div>
      </div>

      {finding.impact && (
        <p className="mt-2 border-l-2 border-clay-500 pl-2.5 text-[12px] leading-snug text-ink-600">
          {finding.impact}
        </p>
      )}

      {finding.evidence.length > 0 && (
        <div className="mt-3">
          <p className="label-mono mb-1.5 text-ink-400">
            evidencia ({finding.evidence.length})
          </p>
          <ul className="space-y-1.5">
            {finding.evidence.map((evidence, index) => (
              <EvidenceRow key={index} evidence={evidence} />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export function AgentDetail({ output }: { output: AgentOutput }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border-2 border-violet-600 bg-violet-50 p-5"
      aria-label={`Detalle de ${agentLabel(output.agent)}`}
    >
      <h3 className="font-display text-[20px] tracking-tightest text-ink-900">
        {agentLabel(output.agent)}
      </h3>
      <p className="mt-1 text-[13px] leading-relaxed text-ink-700">{output.summary}</p>

      {output.missing_information.length > 0 && (
        <div className="mt-4 rounded-lg border-2 border-clay-500 bg-clay-100 p-3">
          <p className="label-mono mb-1.5 text-clay-700">información que falta</p>
          <ul className="space-y-1">
            {output.missing_information.map((item, index) => (
              <li key={index} className="text-[12px] leading-snug text-clay-700">
                · {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {output.findings.length > 0 ? (
        <div className="mt-4 space-y-3">
          {output.findings.map((finding, index) => (
            <FindingCard key={`${finding.code}-${index}`} finding={finding} />
          ))}
        </div>
      ) : (
        <p className="mt-4 flex items-center gap-2 text-[12.5px] text-ink-500">
          <Zap className="h-3.5 w-3.5 text-ink-300" aria-hidden />
          Sin hallazgos con los datos disponibles.
        </p>
      )}
    </motion.section>
  )
}
