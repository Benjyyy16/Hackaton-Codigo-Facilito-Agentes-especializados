import { motion } from 'framer-motion'
import { ArrowUpRight } from 'lucide-react'
import { problemStats, contextStats } from '@/data/content'
import { SectionHeading } from '@/components/ui/SectionHeading'
import { Odometer, Reveal, Scribble, Stagger, StaggerItem, Tilt } from '@/components/ui/Bits'

export function ProblemStats() {
  return (
    <section id="problema" className="relative py-24 sm:py-32">
      <div className="container-page">
        <SectionHeading
          index="01"
          eyebrow="Evidencia del problema"
          align="left"
          title={
            <>
              Nadie duda de que trabajaste.{' '}
              <span className="relative inline-block">
                <span className="italic text-violet-600">Dudan de la prueba.</span>
                <Scribble variant="underline" className="-bottom-2 h-3.5" delay={0.5} />
              </span>
            </>
          }
          subtitle="Las cifras no son nuestras. Cada una enlaza al estudio original para que puedas auditarla."
        />

        {/* Fichas de dato: papel con esquinas de plano */}
        <Stagger className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-4" gap={0.09}>
          {problemStats.map((s, i) => (
            <StaggerItem key={s.label}>
              <Tilt strength={7}>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="corners group block h-full rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard transition-transform hover:-translate-y-1"
                  style={{ rotate: `${(i % 2 === 0 ? -1 : 1) * 0.7}deg` }}
                >
                  {/* franja de encabezado */}
                  <div className="mb-4 flex items-center justify-between border-b-2 border-dashed border-ink-200 pb-2.5">
                    <span className="font-mono text-[9.5px] font-bold uppercase tracking-[0.14em] text-ink-400">
                      dato {String(i + 1).padStart(2, '0')}
                    </span>
                    <ArrowUpRight className="h-3.5 w-3.5 text-ink-300 transition-colors group-hover:text-violet-600" />
                  </div>

                  <p className="font-display text-[46px] leading-none tracking-tightest text-ink-900">
                    <Odometer value={s.value} />
                  </p>
                  <p className="mt-1.5 text-[13px] font-bold uppercase tracking-wide text-violet-700">
                    {s.label}
                  </p>
                  <p className="mt-3 text-[13px] leading-relaxed text-ink-600">{s.detail}</p>

                  <p className="mt-4 flex items-center gap-1.5 border-t border-ink-100 pt-3 font-mono text-[10px] uppercase tracking-wider text-ink-400 transition-colors group-hover:text-violet-600">
                    fuente · {s.source}
                  </p>
                </a>
              </Tilt>
            </StaggerItem>
          ))}
        </Stagger>

        {/* Ledger de contexto IA: tabla reglada */}
        <Reveal delay={0.1} className="mt-8">
          <div className="overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard">
            <div className="flex items-center justify-between border-b-2 border-ink-900 bg-ink-900 px-5 py-2.5">
              <span className="font-mono text-[10.5px] font-bold uppercase tracking-[0.16em] text-white">
                La paradoja de la IA
              </span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-white/45">
                3 registros
              </span>
            </div>

            <div className="divide-y-2 divide-dashed divide-ink-200 md:grid md:grid-cols-3 md:divide-y-0 md:divide-x-2">
              {contextStats.map((s, i) => (
                <motion.a
                  key={s.label}
                  href={s.url}
                  target="_blank"
                  rel="noreferrer noopener"
                  initial={{ opacity: 0, y: 18 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.1, duration: 0.5 }}
                  className="group block p-5 transition-colors hover:bg-violet-50"
                >
                  <div className="flex items-baseline gap-2.5">
                    <span className="font-display text-[34px] leading-none tracking-tightest text-violet-600">
                      <Odometer value={s.value} />
                    </span>
                    <span className="text-[11.5px] font-bold uppercase tracking-wide text-ink-500">
                      {s.label}
                    </span>
                  </div>
                  <p className="mt-3 text-[13px] leading-relaxed text-ink-600">{s.detail}</p>
                  <p className="mt-3 flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-ink-400 group-hover:text-violet-600">
                    {s.source}
                    <ArrowUpRight className="h-3 w-3" />
                  </p>
                </motion.a>
              ))}
            </div>
          </div>
        </Reveal>

        {/* conclusión */}
        <Reveal delay={0.12} className="mt-10">
          <div className="mx-auto flex max-w-2xl items-start gap-4">
            <span className="mt-1 font-display text-[42px] leading-none text-violet-300">“</span>
            <p className="font-display text-[21px] leading-snug text-ink-800 sm:text-[24px]">
              Escribir código más rápido no arregla la entrega.{' '}
              <span className="bg-mint-200 px-1 not-italic">Lo que falta es coordinación</span> y una
              prueba que cualquiera pueda abrir.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
