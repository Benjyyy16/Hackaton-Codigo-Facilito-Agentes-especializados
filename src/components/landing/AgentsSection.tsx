import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Brain, Code2, FileText, LineChart, Search, ShieldCheck } from 'lucide-react'
import { agents, type Agent } from '@/data/content'
import { SectionHeading } from '@/components/ui/SectionHeading'
import { Reveal, ScrambleText } from '@/components/ui/Bits'
import { cn } from '@/lib/cn'

const iconMap: Record<Agent['icon'], React.ElementType> = {
  brain: Brain,
  code: Code2,
  shield: ShieldCheck,
  chart: LineChart,
  search: Search,
  file: FileText,
}

export function AgentsSection() {
  const [open, setOpen] = useState<string>(agents[0].id)

  return (
    <section id="agentes" className="relative py-24 sm:py-32">
      <div className="container-page">
        <SectionHeading
          index="02"
          eyebrow="La tripulación"
          align="left"
          title={
            <>
              Seis especialistas con <span className="italic text-violet-600">expediente</span>.
            </>
          }
          subtitle="Cada agente tiene dominio, entregables y firma. Elegí uno para ver su ficha."
        />

        {/* Lista tipo expediente: filas que se expanden como acordeón */}
        <Reveal delay={0.08} className="mt-14">
          <div className="overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard-lg">
            {/* cabecera de tabla */}
            <div className="hidden grid-cols-[64px_1.1fr_1fr_92px] items-center gap-4 border-b-2 border-ink-900 bg-ink-900 px-5 py-2.5 sm:grid">
              {['cód.', 'agente', 'dominio', 'estado'].map((h) => (
                <span
                  key={h}
                  className="font-mono text-[9.5px] font-bold uppercase tracking-[0.16em] text-white/70"
                >
                  {h}
                </span>
              ))}
            </div>

            <div className="divide-y-2 divide-ink-100">
              {agents.map((a, i) => {
                const Icon = iconMap[a.icon]
                const isOpen = open === a.id
                return (
                  <div key={a.id} className={cn('transition-colors', isOpen && 'bg-violet-50/60')}>
                    <button
                      onClick={() => setOpen(isOpen ? '' : a.id)}
                      aria-expanded={isOpen}
                      className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-4 px-5 py-4 text-left sm:grid-cols-[64px_1.1fr_1fr_92px]"
                    >
                      <span className="font-mono text-[11px] font-bold text-ink-400">
                        AG-{String(i + 1).padStart(2, '0')}
                      </span>

                      <span className="flex min-w-0 items-center gap-3">
                        <span
                          className={cn(
                            'grid h-9 w-9 shrink-0 place-items-center rounded-lg border-2 border-ink-900 transition-colors',
                            isOpen ? 'bg-violet-600 text-white' : 'bg-paper text-violet-600',
                          )}
                        >
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-[15.5px] font-bold text-ink-900">
                            {a.name}
                          </span>
                          <span className="block truncate text-[12px] text-ink-500 sm:hidden">
                            {a.role}
                          </span>
                        </span>
                      </span>

                      <span className="hidden text-[13px] text-ink-600 sm:block">{a.role}</span>

                      <span className="hidden justify-self-end sm:block">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded border-2 px-2 py-0.5 font-mono text-[9.5px] font-bold uppercase tracking-wider',
                            isOpen
                              ? 'border-mint-600 bg-mint-100 text-mint-700'
                              : 'border-ink-200 bg-paper-100 text-ink-400',
                          )}
                        >
                          <motion.span
                            className={cn(
                              'h-1.5 w-1.5 rounded-full',
                              isOpen ? 'bg-mint-500' : 'bg-ink-300',
                            )}
                            animate={isOpen ? { opacity: [1, 0.3, 1] } : {}}
                            transition={{ duration: 1.5, repeat: Infinity }}
                          />
                          {isOpen ? 'activo' : 'listo'}
                        </span>
                      </span>

                      <span className="justify-self-end sm:hidden">
                        <motion.span
                          animate={{ rotate: isOpen ? 45 : 0 }}
                          className="grid h-7 w-7 place-items-center rounded border-2 border-ink-900 font-bold text-ink-900"
                        >
                          +
                        </motion.span>
                      </span>
                    </button>

                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.32, ease: [0.19, 1, 0.22, 1] }}
                          className="overflow-hidden"
                        >
                          <div className="grid gap-6 px-5 pb-6 sm:grid-cols-[1.2fr_1fr] sm:pl-[84px]">
                            <p className="text-[14px] leading-relaxed text-ink-700">{a.blurb}</p>

                            <div>
                              <p className="label-mono mb-2.5 text-ink-400">Entregables</p>
                              <ul className="space-y-1.5">
                                {a.outputs.map((o, k) => (
                                  <motion.li
                                    key={o}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.08 + k * 0.07 }}
                                    className="flex items-center gap-2 text-[13px] text-ink-800"
                                  >
                                    <span className="h-[7px] w-[7px] shrink-0 rotate-45 border-[1.5px] border-ink-900 bg-mint-500" />
                                    <ScrambleText text={o} className="text-[12.5px]" />
                                  </motion.li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )
              })}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
