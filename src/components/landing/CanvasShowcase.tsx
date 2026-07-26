import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Bot, FileText, GitBranch, GitPullRequest, Plus, RefreshCw, User as UserIcon } from 'lucide-react'
import { SectionHeading } from '@/components/ui/SectionHeading'
import { Reveal, Stamp } from '@/components/ui/Bits'
import { GitHubLogo } from '@/components/brand/Logos'
import { cn } from '@/lib/cn'

type Col = 'backlog' | 'progress' | 'review' | 'done'

interface Card {
  id: string
  title: string
  col: Col
  owner: string
  bot: boolean
  ref?: string
}

const columns: { id: Col; label: string; accent: string; head: string }[] = [
  { id: 'backlog', label: 'Backlog', accent: 'bg-ink-300', head: 'bg-paper-200' },
  { id: 'progress', label: 'En curso', accent: 'bg-violet-500', head: 'bg-violet-100' },
  { id: 'review', label: 'Revisión', accent: 'bg-clay-500', head: 'bg-clay-100' },
  { id: 'done', label: 'Hecho', accent: 'bg-mint-500', head: 'bg-mint-100' },
]

const initial: Card[] = [
  { id: 'a', title: 'Webhook con backoff exponencial', col: 'review', owner: 'Constructor', bot: true, ref: 'PR #214' },
  { id: 'b', title: 'Índices en tabla transactions', col: 'done', owner: 'Arquitecto', bot: true, ref: 'PR #211' },
  { id: 'c', title: 'Rediseño del flujo 3DS', col: 'progress', owner: 'Lucía F.', bot: false },
  { id: 'd', title: 'Auditar políticas RLS', col: 'progress', owner: 'Auditor', bot: true, ref: 'feat/rls' },
  { id: 'e', title: 'Reporte de costo por transacción', col: 'backlog', owner: 'Analista', bot: true },
  { id: 'f', title: 'Migrar a Payment Intents v2', col: 'backlog', owner: 'Arquitecto', bot: true, ref: 'issue #198' },
]

const script = [
  { id: 'a', to: 'done' as Col, event: 'PR #214 mergeado por @nora', doc: 'Changelog · 3 archivos' },
  { id: 'd', to: 'review' as Col, event: 'PR #216 abierto desde feat/rls', doc: 'Docs de seguridad' },
  { id: 'e', to: 'progress' as Col, event: 'Rama feat/cost-report creada', doc: 'Spec técnica añadida' },
]

export function CanvasShowcase() {
  const [cards, setCards] = useState<Card[]>(initial)
  const [log, setLog] = useState<{ event: string; doc: string }[]>([])
  const [syncing, setSyncing] = useState(false)
  const step = useRef(0)

  useEffect(() => {
    const timers = new Set<number>()
    const later = (fn: () => void, ms: number) => {
      const id = window.setTimeout(() => {
        timers.delete(id)
        fn()
      }, ms)
      timers.add(id)
    }

    const run = () => {
      const s = script[step.current % script.length]
      setSyncing(true)
      later(() => {
        setCards((prev) => prev.map((c) => (c.id === s.id ? { ...c, col: s.to } : c)))
        setLog((prev) => [{ event: s.event, doc: s.doc }, ...prev].slice(0, 3))
        setSyncing(false)
        step.current += 1
        if (step.current % script.length === 0) later(() => setCards(initial), 2600)
      }, 1100)
    }

    const interval = window.setInterval(run, 4200)
    later(run, 1400)
    return () => {
      window.clearInterval(interval)
      timers.forEach((id) => window.clearTimeout(id))
      timers.clear()
    }
  }, [])

  return (
    <section id="tablero" className="relative py-24 sm:py-32">
      <div className="container-page">
        <SectionHeading
          index="03"
          eyebrow="Tablero canvas"
          align="left"
          title={
            <>
              Se mueve porque <span className="italic text-violet-600">el código se movió</span>.
            </>
          }
          subtitle="Conectá el repositorio y las tarjetas dejan de ser una promesa manual. Mirá: esto avanza solo."
        />

        <Reveal delay={0.08} className="mt-14">
          <div className="overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard-lg">
            {/* barra de aplicación */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-ink-900 bg-paper-100 px-4 py-2.5">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  {['bg-ink-300', 'bg-ink-300', 'bg-mint-500'].map((c, i) => (
                    <span
                      key={i}
                      className={cn('h-2.5 w-2.5 rounded-full border border-ink-900', c)}
                    />
                  ))}
                </div>
                <span className="text-[13px] font-bold text-ink-900">Nébula Checkout</span>
                <span className="hidden items-center gap-1.5 rounded border-2 border-ink-200 bg-paper px-2 py-0.5 font-mono text-[10px] text-ink-600 sm:inline-flex">
                  <GitHubLogo className="h-3 w-3" />
                  nebula-labs/checkout-core
                </span>
              </div>

              <AnimatePresence mode="wait">
                <motion.span
                  key={syncing ? 'sync' : 'idle'}
                  initial={{ opacity: 0, y: -5 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 5 }}
                  className={cn(
                    'inline-flex items-center gap-1.5 rounded border-2 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider',
                    syncing
                      ? 'border-violet-600 bg-violet-100 text-violet-700'
                      : 'border-mint-600 bg-mint-100 text-mint-700',
                  )}
                >
                  <RefreshCw className={cn('h-3 w-3', syncing && 'animate-spin')} />
                  {syncing ? 'sync…' : 'al día'}
                </motion.span>
              </AnimatePresence>
            </div>

            {/* columnas */}
            <div className="grid gap-0 divide-y-2 divide-ink-100 sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4 lg:divide-x-2">
              {columns.map((col) => {
                const items = cards.filter((c) => c.col === col.id)
                return (
                  <div key={col.id} className="min-w-0">
                    <div
                      className={cn(
                        'flex items-center justify-between border-b-2 border-ink-100 px-3.5 py-2',
                        col.head,
                      )}
                    >
                      <span className="flex items-center gap-2 font-mono text-[10.5px] font-bold uppercase tracking-[0.13em] text-ink-800">
                        <span className={cn('h-2 w-2 border border-ink-900', col.accent)} />
                        {col.label}
                      </span>
                      <span className="font-mono text-[10.5px] font-bold text-ink-500">
                        {items.length}
                      </span>
                    </div>

                    <div className="flex min-h-[210px] flex-col gap-2 p-3">
                      <AnimatePresence mode="popLayout">
                        {items.map((c) => (
                          <motion.div
                            key={c.id}
                            layout
                            layoutId={c.id}
                            initial={{ opacity: 0, scale: 0.9, rotate: -3 }}
                            animate={{ opacity: 1, scale: 1, rotate: 0 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            transition={{
                              type: 'spring',
                              stiffness: 340,
                              damping: 28,
                              layout: { duration: 0.5 },
                            }}
                            className={cn(
                              'relative cursor-grab rounded-lg border-2 border-ink-900 p-2.5 shadow-hard-sm',
                              c.col === 'done' ? 'bg-mint-50' : 'bg-paper',
                            )}
                          >
                            <p className="pr-1 text-[12.5px] font-semibold leading-snug text-ink-900">
                              {c.title}
                            </p>
                            <div className="mt-2 flex items-center justify-between gap-2">
                              <span className="flex min-w-0 items-center gap-1.5 text-[10px] font-medium text-ink-500">
                                {c.bot ? (
                                  <Bot className="h-3 w-3 shrink-0 text-violet-600" />
                                ) : (
                                  <UserIcon className="h-3 w-3 shrink-0 text-mint-600" />
                                )}
                                <span className="truncate">{c.owner}</span>
                              </span>
                              {c.ref && (
                                <span className="flex shrink-0 items-center gap-1 rounded border border-ink-200 bg-paper-100 px-1.5 py-0.5 font-mono text-[9px] font-medium text-ink-600">
                                  {c.ref.startsWith('PR') ? (
                                    <GitPullRequest className="h-2.5 w-2.5" />
                                  ) : (
                                    <GitBranch className="h-2.5 w-2.5" />
                                  )}
                                  {c.ref}
                                </span>
                              )}
                            </div>

                            {c.col === 'done' && (
                              <div className="absolute -right-1.5 -top-2.5">
                                <Stamp
                                  tone="mint"
                                  className="!border-[1.5px] !px-1.5 !py-0 !text-[8px]"
                                >
                                  verificado
                                </Stamp>
                              </div>
                            )}
                          </motion.div>
                        ))}
                      </AnimatePresence>

                      {col.id === 'backlog' && (
                        <button className="group flex items-center justify-center gap-1.5 rounded-lg border-2 border-dashed border-ink-200 py-2.5 font-mono text-[10.5px] uppercase tracking-wider text-ink-400 transition-colors hover:border-violet-600 hover:text-violet-700">
                          <Plus className="h-3 w-3" />
                          pedir a un agente
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* bitácora del repo */}
            <div className="border-t-2 border-ink-900 bg-ink-900 px-4 py-3">
              <p className="mb-2 font-mono text-[9.5px] font-bold uppercase tracking-[0.16em] text-white/45">
                eventos del repositorio
              </p>
              <div className="min-h-[66px] space-y-1.5">
                <AnimatePresence mode="popLayout">
                  {log.length === 0 && (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="font-mono text-[11.5px] text-white/30"
                    >
                      esperando actividad en main
                      <span className="ml-0.5 animate-blink">▊</span>
                    </motion.p>
                  )}
                  {log.map((l, i) => (
                    <motion.div
                      key={l.event + i}
                      layout
                      initial={{ opacity: 0, x: -16 }}
                      animate={{ opacity: 1 - i * 0.3, x: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.35 }}
                      className="flex flex-wrap items-center gap-x-2.5 gap-y-1 font-mono text-[11.5px]"
                    >
                      <span className="text-mint-400">→</span>
                      <span className="text-white/85">{l.event}</span>
                      <span className="inline-flex items-center gap-1 rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-white/60">
                        <FileText className="h-2.5 w-2.5" />
                        {l.doc}
                      </span>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </Reveal>

        {/* tres notas al pie, con estética de post-it */}
        <div className="mt-10 grid gap-5 sm:grid-cols-3">
          {[
            {
              t: 'Un tablero por proyecto',
              d: 'Proyecto 1 con su repo, proyecto 2 con el suyo. Espacios aislados, agentes propios.',
              rot: -1.2,
            },
            {
              t: 'Docs derivadas del diff',
              d: 'El Cronista lee el cambio real, no lo que alguien recordó escribir en la wiki.',
              rot: 0.8,
            },
            {
              t: 'Tarjetas con procedencia',
              d: 'Cada tarjeta enlaza a su PR, rama o issue. El avance se abre y se verifica.',
              rot: -0.6,
            },
          ].map((b, i) => (
            <Reveal key={b.t} delay={i * 0.08} direction="skew">
              <div
                className="h-full rounded-lg border-2 border-ink-900 bg-paper p-5 shadow-hard transition-transform hover:-translate-y-1 hover:rotate-0"
                style={{ rotate: `${b.rot}deg` }}
              >
                <span className="mb-3 block h-1 w-8 bg-violet-600" />
                <p className="text-[14.5px] font-bold text-ink-900">{b.t}</p>
                <p className="mt-2 text-[13px] leading-relaxed text-ink-600">{b.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
