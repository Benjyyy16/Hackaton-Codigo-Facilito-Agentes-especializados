import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Plus } from 'lucide-react'
import { integrations, type Integration } from '@/data/content'
import { SectionHeading } from '@/components/ui/SectionHeading'
import { Reveal, Stagger, StaggerItem } from '@/components/ui/Bits'
import { FlowDiagram } from './FlowDiagram'
import {
  FigmaLogo,
  GitHubLogo,
  LinearLogo,
  NotionLogo,
  SlackLogo,
  StripeLogo,
  SupabaseLogo,
  VercelLogo,
} from '@/components/brand/Logos'
import { cn } from '@/lib/cn'

const logoMap: Record<string, React.ReactNode> = {
  github: <GitHubLogo className="h-6 w-6 text-ink-900" />,
  supabase: <SupabaseLogo className="h-6 w-6" />,
  vercel: <VercelLogo className="h-5 w-5 text-ink-900" />,
  slack: <SlackLogo className="h-6 w-6" />,
  linear: <LinearLogo className="h-6 w-6 text-ink-900" />,
  notion: <NotionLogo className="h-6 w-6" />,
  figma: <FigmaLogo className="h-6 w-[18px]" />,
  stripe: <StripeLogo className="h-6 w-6" />,
}

const statusMeta: Record<Integration['status'], { label: string; cls: string }> = {
  live: { label: 'activo', cls: 'border-mint-600 bg-mint-100 text-mint-700' },
  beta: { label: 'beta', cls: 'border-violet-600 bg-violet-100 text-violet-700' },
  soon: { label: 'pronto', cls: 'border-ink-200 bg-paper-100 text-ink-400' },
}

export function Integrations() {
  const [open, setOpen] = useState<string | null>('github')

  return (
    <section id="conexiones" className="relative py-24 sm:py-32">
      <div className="container-page">
        <SectionHeading
          index="04"
          eyebrow="Conexiones"
          align="left"
          title={
            <>
              Tus herramientas ya tienen la verdad.{' '}
              <span className="italic text-violet-600">Nosotros la leemos.</span>
            </>
          }
          subtitle="No migres nada. Orquesta se monta encima de tu stack y deja el repositorio como fuente de verdad."
        />

        {/* Grilla de fichas con logos originales */}
        <Stagger className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" gap={0.06}>
          {integrations.map((it) => {
            const isOpen = open === it.id
            const S = statusMeta[it.status]
            return (
              <StaggerItem key={it.id}>
                <motion.button
                  type="button"
                  onClick={() => setOpen(isOpen ? null : it.id)}
                  aria-expanded={isOpen}
                  whileHover={{ y: -4 }}
                  transition={{ type: 'spring', stiffness: 380, damping: 24 }}
                  className={cn(
                    'group flex h-full w-full flex-col rounded-xl border-2 border-ink-900 p-4 text-left shadow-hard',
                    isOpen ? 'bg-violet-50' : 'bg-paper',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg border-2 border-ink-900 bg-paper transition-transform duration-300 group-hover:-rotate-6">
                      {logoMap[it.id]}
                    </span>
                    <span
                      className={cn(
                        'rounded border-2 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider',
                        S.cls,
                      )}
                    >
                      {S.label}
                    </span>
                  </div>

                  <div className="mt-4">
                    <div className="flex items-baseline gap-2">
                      <h3 className="text-[15.5px] font-bold text-ink-900">{it.name}</h3>
                      <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
                        {it.category}
                      </span>
                    </div>
                    <p className="mt-1.5 text-[12.5px] leading-relaxed text-ink-600">{it.what}</p>
                  </div>

                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.28 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-3.5 border-t-2 border-dashed border-ink-200 pt-3">
                          <p className="label-mono mb-2 text-ink-400">los agentes leen</p>
                          <div className="flex flex-wrap gap-1.5">
                            {it.reads.map((r, i) => (
                              <motion.span
                                key={r}
                                initial={{ opacity: 0, scale: 0.85 }}
                                animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: i * 0.05 }}
                                className="rounded border border-ink-900 bg-paper px-1.5 py-0.5 font-mono text-[9.5px] font-medium text-ink-800"
                              >
                                {r}
                              </motion.span>
                            ))}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <motion.span
                    animate={{ rotate: isOpen ? 45 : 0 }}
                    className="mt-auto self-end pt-3 text-ink-300 transition-colors group-hover:text-violet-600"
                  >
                    <Plus className="h-4 w-4" />
                  </motion.span>
                </motion.button>
              </StaggerItem>
            )
          })}
        </Stagger>

        {/* Diagrama */}
        <div className="mt-20">
          <SectionHeading
            eyebrow="Plano de recorrido"
            align="left"
            title={
              <>
                Del commit al reporte, <span className="italic text-violet-600">sin intermediarios</span>
              </>
            }
          />
          <Reveal delay={0.08} className="mt-8">
            <FlowDiagram />
          </Reveal>
        </div>
      </div>
    </section>
  )
}
