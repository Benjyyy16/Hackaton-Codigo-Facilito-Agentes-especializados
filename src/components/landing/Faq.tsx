import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { faqs } from '@/data/content'
import { SectionHeading } from '@/components/ui/SectionHeading'
import { Reveal } from '@/components/ui/Bits'
import { cn } from '@/lib/cn'

export function Faq() {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="relative py-24 sm:py-32">
      <div className="container-page">
        <div className="grid gap-12 lg:grid-cols-[.85fr_1.15fr]">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <SectionHeading
              index="07"
              eyebrow="Dudas razonables"
              align="left"
              title={
                <>
                  Las preguntas que <span className="italic text-violet-600">deberías hacer.</span>
                </>
              }
            />
          </div>

          <div className="divide-y-2 divide-ink-100 border-y-2 border-ink-900">
            {faqs.map((f, i) => {
              const isOpen = open === i
              return (
                <Reveal key={f.q} delay={i * 0.04}>
                  <div className={cn('transition-colors', isOpen && 'bg-violet-50/50')}>
                    <button
                      onClick={() => setOpen(isOpen ? null : i)}
                      aria-expanded={isOpen}
                      className="group flex w-full items-start gap-4 py-5 text-left"
                    >
                      <span className="mt-0.5 shrink-0 font-mono text-[11px] font-bold text-ink-300">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <span className="flex-1 text-[15px] font-bold leading-snug text-ink-900">
                        {f.q}
                      </span>
                      <motion.span
                        animate={{ rotate: isOpen ? 135 : 0 }}
                        transition={{ duration: 0.25 }}
                        className={cn(
                          'grid h-7 w-7 shrink-0 place-items-center rounded border-2 font-bold leading-none transition-colors',
                          isOpen
                            ? 'border-violet-600 bg-violet-600 text-white'
                            : 'border-ink-900 bg-paper text-ink-900 group-hover:bg-violet-100',
                        )}
                      >
                        +
                      </motion.span>
                    </button>

                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.3, ease: [0.19, 1, 0.22, 1] }}
                          className="overflow-hidden"
                        >
                          <p className="pb-5 pl-[38px] pr-11 text-[13.5px] leading-relaxed text-ink-600">
                            {f.a}
                          </p>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </Reveal>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
