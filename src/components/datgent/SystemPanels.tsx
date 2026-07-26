import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  Activity,
  CheckCircle2,
  CircleHelp,
  Database,
  Lightbulb,
  Lock,
  Radio,
  ShieldCheck,
} from 'lucide-react'
import { agentLabel, datgent } from '@/lib/datgentApi'
import type { HealthResponse, ProposedAction, RiskCase, SchemaStatus } from '@/lib/datgentTypes'
import { useDatgentEvents } from '@/hooks/useDatgentEvents'
import { cn } from '@/lib/cn'

// ---------------------------------------------------------------------------------
// Hechos, inferencias, supuestos y huecos
// ---------------------------------------------------------------------------------

export function ClaimsPanel({ riskCase }: { riskCase: RiskCase }) {
  const columns = [
    {
      title: 'Hechos',
      hint: 'Observados en un proveedor',
      items: riskCase.facts,
      tone: 'border-mint-500 bg-mint-50',
      label: 'text-mint-700',
    },
    {
      title: 'Inferencias',
      hint: 'Derivadas por heurística',
      items: riskCase.inferences,
      tone: 'border-violet-600 bg-violet-50',
      label: 'text-violet-700',
    },
    {
      title: 'Supuestos',
      hint: 'Se aceptan sin verificar',
      items: riskCase.assumptions,
      tone: 'border-clay-500 bg-clay-100',
      label: 'text-clay-700',
    },
    {
      title: 'Información que falta',
      hint: 'No se pudo comprobar',
      items: riskCase.missing_information,
      tone: 'border-ink-300 bg-ink-50',
      label: 'text-ink-600',
    },
  ]

  return (
    <div className="grid gap-3 lg:grid-cols-4">
      {columns.map((column) => (
        <div
          key={column.title}
          className={cn('rounded-xl border-2 p-4', column.tone)}
        >
          <p className={cn('label-mono', column.label)}>{column.title}</p>
          <p className="mt-0.5 font-mono text-[9.5px] text-ink-400">{column.hint}</p>
          <p className="mt-1 font-display text-[24px] leading-none text-ink-900">
            {column.items.length}
          </p>
          <ul className="mt-2.5 space-y-1.5">
            {column.items.map((item, index) => (
              <li key={index} className="text-[11.5px] leading-snug text-ink-700">
                · {item}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------------
// Acciones propuestas
// ---------------------------------------------------------------------------------

export function ProposedActions({
  actions,
  persistenceReady,
}: {
  actions: ProposedAction[]
  persistenceReady: boolean
}) {
  return (
    <div className="space-y-3">
      {!persistenceReady && (
        <p className="flex items-start gap-2 rounded-lg border-2 border-clay-500 bg-clay-100 p-3 text-[12.5px] leading-snug text-clay-700">
          <Lock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            Estas acciones son <strong>propuestas</strong>: todavía no existen como
            decisiones registradas. Aprobar o rechazar de verdad requiere la persistencia
            activa, porque una aprobación sin registro de quién y cuándo no serviría de
            auditoría.
          </span>
        </p>
      )}

      {actions.map((action, index) => (
        <motion.article
          key={`${action.action_type}-${index}`}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.05 }}
          className="rounded-xl border-2 border-ink-900 bg-paper p-4 shadow-hard-sm"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <code className="rounded bg-ink-100 px-1.5 py-0.5 font-mono text-[10px] font-bold text-ink-700">
                  {action.action_type}
                </code>
                <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
                  {agentLabel(action.agent)}
                </span>
              </div>
              <h4 className="mt-1.5 text-[13.5px] font-bold leading-snug text-ink-900">
                {action.title}
              </h4>
              <p className="mt-1 text-[12px] leading-snug text-ink-600">
                {action.rationale}
              </p>
            </div>
            {action.requires_human_approval && (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full border-2 border-violet-600 bg-violet-50 px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-violet-700">
                <ShieldCheck className="h-3 w-3" aria-hidden />
                requiere aprobación
              </span>
            )}
          </div>

          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled
              title="Aprobar requiere la persistencia activa: sin registro no hay auditoría."
              className="rounded-lg border-2 border-ink-300 bg-ink-50 px-3 py-1.5 text-[11.5px] font-bold text-ink-400"
            >
              Aprobar
            </button>
            <button
              type="button"
              disabled
              title="Rechazar requiere la persistencia activa: sin registro no hay auditoría."
              className="rounded-lg border-2 border-ink-300 bg-ink-50 px-3 py-1.5 text-[11.5px] font-bold text-ink-400"
            >
              Rechazar
            </button>
          </div>
        </motion.article>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------------
// Estado del sistema
// ---------------------------------------------------------------------------------

export function SystemStatus({
  onSchemaStatus,
}: {
  onSchemaStatus?: (status: SchemaStatus) => void
}) {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [schema, setSchema] = useState<SchemaStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    // Las dos sondas van en paralelo y cada una absorbe su propio fallo: que el estado del
    // esquema no se pueda leer no debe ocultar el de salud.
    void Promise.allSettled([datgent.health(), datgent.schemaStatus()]).then(
      ([healthResult, schemaResult]) => {
        if (cancelled) return
        if (healthResult.status === 'fulfilled') setHealth(healthResult.value)
        if (schemaResult.status === 'fulfilled') {
          setSchema(schemaResult.value)
          onSchemaStatus?.(schemaResult.value)
        }
        setLoading(false)
      },
    )

    return () => {
      cancelled = true
    }
  }, [onSchemaStatus])

  return (
    <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-violet-600" aria-hidden />
        <h3 className="text-[15px] font-bold text-ink-900">Estado del sistema</h3>
      </div>

      {loading ? (
        <p className="mt-3 text-[12.5px] text-ink-500">Consultando el backend…</p>
      ) : (
        <div className="mt-3 space-y-3">
          {health ? (
            <div>
              <div className="flex items-center justify-between">
                <span className="text-[12.5px] text-ink-600">Servicio</span>
                <span
                  className={cn(
                    'rounded-full border px-2 py-0.5 font-mono text-[9.5px] font-bold uppercase',
                    health.status === 'ok'
                      ? 'border-mint-300 bg-mint-100 text-mint-700'
                      : 'border-clay-300 bg-clay-100 text-clay-700',
                  )}
                >
                  {health.status === 'ok' ? 'operativo' : 'degradado'}
                </span>
              </div>
              <p className="mt-1 font-mono text-[10px] text-ink-400">
                {health.service} v{health.version} · {health.environment}
              </p>
              <ul className="mt-2 space-y-1">
                {health.dependencies.map((dependency) => (
                  <li
                    key={dependency.name}
                    className="flex items-center justify-between font-mono text-[10.5px]"
                  >
                    <span className="text-ink-500">{dependency.name}</span>
                    <span
                      className={
                        dependency.status === 'up' ? 'text-mint-700' : 'text-rose-600'
                      }
                    >
                      {dependency.status}
                      {dependency.latency_ms !== null && ` · ${dependency.latency_ms}ms`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-[12.5px] text-ink-500">No se pudo leer el estado de salud.</p>
          )}

          {schema && (
            <div className="border-t-2 border-dashed border-ink-200 pt-3">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[12.5px] text-ink-600">
                  <Database className="h-3.5 w-3.5" aria-hidden />
                  Esquema
                </span>
                <span
                  className={cn(
                    'rounded-full border px-2 py-0.5 font-mono text-[9.5px] font-bold uppercase',
                    schema.ready
                      ? 'border-mint-300 bg-mint-100 text-mint-700'
                      : 'border-clay-300 bg-clay-100 text-clay-700',
                  )}
                >
                  {schema.tables.filter((table) => table.exists).length}/
                  {schema.tables.length} tablas
                </span>
              </div>
              <p className="mt-1.5 text-[11.5px] leading-snug text-ink-600">{schema.hint}</p>
              {schema.missing.length > 0 && (
                <p className="mt-1.5 font-mono text-[10px] leading-snug text-clay-700">
                  faltan: {schema.missing.join(', ')}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------------
// Eventos en vivo
// ---------------------------------------------------------------------------------

export function LiveEventFeed() {
  const { events, state } = useDatgentEvents()

  const stateLabel: Record<typeof state, string> = {
    connecting: 'conectando',
    open: 'en vivo',
    closed: 'desconectado',
    error: 'sin conexión',
  }

  return (
    <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
      <div className="flex items-center gap-2">
        <Radio className="h-4 w-4 text-violet-600" aria-hidden />
        <h3 className="text-[15px] font-bold text-ink-900">Eventos en vivo</h3>
        <span
          className={cn(
            'ml-auto rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold uppercase',
            state === 'open'
              ? 'border-mint-300 bg-mint-100 text-mint-700'
              : 'border-ink-200 bg-ink-50 text-ink-500',
          )}
        >
          {stateLabel[state]}
        </span>
      </div>

      {events.length === 0 ? (
        <p className="mt-3 text-[12px] leading-snug text-ink-500">
          {state === 'open'
            ? 'Canal abierto. Los eventos aparecen cuando el backend ejecuta un análisis persistido.'
            : 'Sin conexión al canal de eventos. El análisis sin persistencia no emite eventos.'}
        </p>
      ) : (
        <ul className="mt-3 max-h-[220px] space-y-1.5 overflow-y-auto">
          {events.map((event, index) => (
            <li
              key={`${event.occurred_at}-${index}`}
              className="flex items-baseline gap-2 rounded border border-ink-200 px-2 py-1.5"
            >
              <code className="font-mono text-[10px] font-bold text-violet-700">
                {event.type}
              </code>
              <span className="ml-auto font-mono text-[9.5px] text-ink-400">
                {new Date(event.occurred_at).toLocaleTimeString('es')}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------------
// Aviso de persistencia
// ---------------------------------------------------------------------------------

export function PersistenceNotice({ schema }: { schema: SchemaStatus | null }) {
  if (schema?.ready) {
    return (
      <p className="flex items-start gap-2 rounded-lg border-2 border-mint-500 bg-mint-50 p-3 text-[12.5px] leading-snug text-mint-700">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <span>
          El esquema está aplicado: el análisis persistido, las alertas y las decisiones con
          aprobación están disponibles.
        </span>
      </p>
    )
  }

  return (
    <p className="flex items-start gap-2 rounded-lg border-2 border-clay-500 bg-clay-100 p-3 text-[12.5px] leading-snug text-clay-700">
      <CircleHelp className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <span>
        Este análisis <strong>no se guarda</strong>. El pipeline se ejecuta completo y el
        resultado es real, pero no hay registro de auditoría, ni alerta, ni decisión
        aprobable hasta que se aplique <code className="font-mono">db/schema.sql</code> en
        Supabase.
        {schema && schema.missing.length > 0 && (
          <> Faltan {schema.missing.length} de {schema.tables.length} tablas.</>
        )}
      </span>
    </p>
  )
}

export { Lightbulb }
