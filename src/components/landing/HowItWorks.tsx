import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { flowSteps } from '@/data/content'
import { SectionHeading } from '@/components/ui/SectionHeading'

export function HowItWorks() {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start 0.85', 'end 0.45'] })
  const grow = useTransform(scrollYProgress, [0, 1], ['0%', '100%'])

  return (
    <section id="como-funciona" className="relative py-24 sm:py-32">
      <div className="container-page">
        <SectionHeading
          index="06"
          eyebrow="Procedimiento"
          align="left"
          title={
            <>
              Cinco pasos. Ninguno es{' '}
              <span className="italic text-violet-600">"confiá en mí"</span>.
            </>
          }
        />

        <div ref={ref} className="relative mt-16">
          {/* riel horizontal en desktop, vertical en móvil */}
          <div className="absolute left-7 top-3 hidden h-[calc(100%-24px)] w-[3px] bg-ink-100 lg:hidden">
            <motion.div style={{ height: grow }} className="w-full bg-violet-600" />
          </div>

          <div className="hidden lg:block">
            <div className="absolute left-0 right-0 top-[27px] h-[3px] bg-ink-100">
              <motion.div style={{ width: grow }} className="h-full bg-violet-600" />
            </div>
          </div>

          <div className="grid gap-8 lg:grid-cols-5 lg:gap-4">
            {flowSteps.map((s, i) => (
              <motion.div
                key={s.n}
                initial={{ opacity: 0, y: 26 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.5 }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="relative flex gap-5 lg:flex-col lg:gap-0"
              >
                {/* nodo numerado */}
                <motion.div
                  initial={{ scale: 0.4, rotate: -25 }}
                  whileInView={{ scale: 1, rotate: 0 }}
                  viewport={{ once: true, amount: 0.7 }}
                  transition={{ type: 'spring', stiffness: 280, damping: 16, delay: i * 0.08 }}
                  className="relative z-10 grid h-14 w-14 shrink-0 place-items-center rounded-lg border-2 border-ink-900 bg-paper font-mono text-[15px] font-bold text-ink-900 shadow-hard"
                >
                  {s.n}
                  <span className="absolute -bottom-1 -right-1 h-3 w-3 border-2 border-ink-900 bg-violet-600" />
                </motion.div>

                <div className="lg:mt-5 lg:pr-3">
                  <h3 className="text-[16px] font-bold leading-snug tracking-tight text-ink-900">
                    {s.title}
                  </h3>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-600">{s.body}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
