import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { TrendingDown, TrendingUp } from 'lucide-react'
import { useCases } from '@/data/content'
import { SectionHeading } from '@/components/ui/SectionHeading'
import { Odometer, Reveal, Stamp } from '@/components/ui/Bits'
import { GitHubLogo } from '@/components/brand/Logos'
import { cn } from '@/lib/cn'

export function UseCases() {
  const [active, setActive] = useState(0)
  const uc = useCases[active]

  return (
    <section id="casos" className="relative py-24 sm:py-32">
      <div className="container-page">
        <SectionHeading
          index="05"
          eyebrow="Casos de uso"
          align="left"
          title={
            <>
              Finanzas también <span className="italic text-violet-600">necesita ver el código.</span>
            </>
          }
          subtitle="Un proyecto se defiende con artefactos, no con diapositivas. Elegí un perfil."
        />

        {/* Pestañas tipo carpeta de archivo */}
        <Reveal delay={0.06} className="mt-12">
          <div role="tablist" aria-label="Casos de uso" className="flex flex-wrap items-end gap-1">
            {useCases.map((c, i) => (
              <button
                key={c.id}
                role="tab"
                aria-selected={active === i}
                onClick={() => setActive(i)}
                className={cn(
                  'relative rounded-t-lg border-2 border-b-0 px-4 pb-3 pt-2.5 font-mono text-[11px] font-bold uppercase tracking-wider transition-colors',
                  active === i
                    ? 'z-10 border-ink-900 bg-violet-600 text-white'
                    : 'border-ink-200 bg-paper-200 text-ink-500 hover:border-ink-900 hover:text-ink-900',
                )}
                style={{ marginBottom: active === i ? -2 : 0 }}
              >
                {c.audience}
                {active === i && (
                  <motion.span
                    layoutId="tab-tick"
                    className="absolute -bottom-[2px] left-1/2 h-[2px] w-8 -translate-x-1/2 bg-violet-600"
                  />
                )}
              </button>
            ))}
          </div>

          {/* Panel */}
          <div className="overflow-hidden rounded-b-xl rounded-tr-xl border-2 border-ink-900 bg-paper shadow-hard-lg">
            <div className="grid lg:grid-cols-[1.08fr_.92fr]">
              {/* Texto */}
              <div className="p-6 sm:p-9">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={uc.id}
                    initial={{ opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -14 }}
                    transition={{ duration: 0.3 }}
                  >
                    <h3 className="font-display text-[27px] leading-tight tracking-tightest text-ink-900 sm:text-[32px]">
                      {uc.title}
                    </h3>

                    <div className="mt-7 space-y-0">
                      {/* Hoy */}
                      <div className="flex gap-4 border-l-[3px] border-clay-500 pl-4">
                        <div>
                          <p className="label-mono mb-1 text-clay-700">hoy</p>
                          <p className="text-[14px] leading-relaxed text-ink-600">{uc.problem}</p>
                        </div>
                      </div>
                      {/* flecha */}
                      <div className="py-3 pl-4">
                        <svg viewBox="0 0 14 26" className="h-6 w-3.5 text-ink-300">
                          <path
                            d="M7 1v20M7 25l-5-6M7 25l5-6"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                            strokeLinecap="round"
                          />
                        </svg>
                      </div>
                      {/* Con Orquesta */}
                      <div className="flex gap-4 border-l-[3px] border-mint-500 pl-4">
                        <div>
                          <p className="label-mono mb-1 text-mint-700">con orquesta</p>
                          <p className="text-[14px] leading-relaxed text-ink-800">{uc.solution}</p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-7 grid gap-2 sm:grid-cols-3">
                      {uc.metrics.map((m, i) => (
                        <motion.div
                          key={m.label}
                          initial={{ opacity: 0, y: 12 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: 0.1 + i * 0.07 }}
                          className="rounded-lg border-2 border-ink-900 bg-paper-100 px-3 py-2.5"
                        >
                          <p className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
                            {m.label}
                          </p>
                          <p className="mt-1 text-[12.5px] font-bold text-ink-900">{m.value}</p>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Libro de costos */}
              <div className="border-t-2 border-ink-900 bg-paper-100 p-6 sm:p-8 lg:border-l-2 lg:border-t-0">
                <Ledger />
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}

/* ================================================================== */
/* Libro de costos: cada monto anclado a PRs                           */
/* ================================================================== */

const rows = [
  { name: 'Conciliación bancaria', cost: 11400, prs: 14, trend: 'up' as const, ref: '#198–#211' },
  { name: 'Flujo 3DS', cost: 8200, prs: 9, trend: 'down' as const, ref: '#180–#194' },
  { name: 'Motor de reintentos', cost: 6100, prs: 7, trend: 'up' as const, ref: '#214' },
  { name: 'Auditoría RLS', cost: 3950, prs: 4, trend: 'down' as const, ref: '#216' },
]

const total = rows.reduce((s, r) => s + r.cost, 0)
const allocated = 48000
const pct = Math.round((total / allocated) * 100)

function Ledger() {
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="label-mono text-ink-400">libro de costos · sprint 14</p>
          <p className="mt-2 font-display text-[34px] leading-none tracking-tightest text-ink-900">
            $<Odometer value={total.toLocaleString('en-US')} />
          </p>
          <p className="mt-1.5 font-mono text-[11px] text-ink-500">
            de ${allocated.toLocaleString('en-US')} · {pct}% consumido
          </p>
        </div>
        <Stamp tone="violet" delay={0.3}>
          <GitHubLogo className="h-2.5 w-2.5" />
          auditado
        </Stamp>
      </div>

      {/* barra segmentada */}
      <div className="mt-5 flex h-3 gap-[2px] overflow-hidden rounded border-2 border-ink-900 bg-paper p-[2px]">
        {Array.from({ length: 20 }, (_, i) => (
          <motion.span
            key={i}
            className={cn('flex-1', i < Math.round(pct / 5) ? 'bg-violet-600' : 'bg-ink-100')}
            initial={{ opacity: 0, scaleY: 0 }}
            whileInView={{ opacity: 1, scaleY: 1 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.03, duration: 0.25 }}
          />
        ))}
      </div>

      {/* filas regladas */}
      <div className="mt-6 divide-y-2 divide-dashed divide-ink-200 border-y-2 border-ink-900">
        {rows.map((r, i) => (
          <motion.div
            key={r.name}
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.08, duration: 0.45 }}
            className="group flex items-center gap-3 py-2.5 transition-colors hover:bg-violet-50"
          >
            <span
              className={cn(
                'h-6 w-1 shrink-0',
                r.trend === 'up' ? 'bg-clay-500' : 'bg-mint-500',
              )}
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[12.5px] font-semibold text-ink-900">{r.name}</p>
              <p className="font-mono text-[9.5px] text-ink-400">
                {r.prs} PRs · {r.ref}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-[13px] font-bold tabular-nums text-ink-900">
                ${r.cost.toLocaleString('en-US')}
              </p>
              <p
                className={cn(
                  'flex items-center justify-end gap-0.5 font-mono text-[9px] font-medium uppercase',
                  r.trend === 'up' ? 'text-clay-700' : 'text-mint-700',
                )}
              >
                {r.trend === 'up' ? (
                  <TrendingUp className="h-2.5 w-2.5" />
                ) : (
                  <TrendingDown className="h-2.5 w-2.5" />
                )}
                {r.trend === 'up' ? 'sobre plan' : 'bajo plan'}
              </p>
            </div>
          </motion.div>
        ))}
      </div>

      <p className="mt-5 border-l-[3px] border-violet-600 pl-3 font-display text-[15px] italic leading-snug text-ink-700">
        Cada monto se abre y muestra los commits que lo generaron. Eso es lo que un CFO puede firmar.
      </p>
    </div>
  )
}
