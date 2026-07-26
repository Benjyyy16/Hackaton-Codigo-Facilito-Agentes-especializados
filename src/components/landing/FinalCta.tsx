import { motion } from 'framer-motion'
import { ArrowRight, PlayCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Marquee, Reveal, Scribble } from '@/components/ui/Bits'
import { GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'

export function FinalCta({
  onOpenAuth,
  onDemo,
}: {
  onOpenAuth: (mode: 'login' | 'signup') => void
  onDemo: () => void
}) {
  return (
    <section className="relative pb-8 pt-16 sm:pt-24">
      <div className="container-page">
        <Reveal direction="scale">
          <div className="paper-grain relative overflow-hidden rounded-2xl border-2 border-ink-900 bg-paper shadow-hard-lg">
            {/* franja diagonal morada arriba */}
            <div className="h-2 bg-hatch bg-[length:9px_9px]" />

            <div className="relative px-7 py-12 text-center sm:px-14 sm:py-16">
              {/* marcas de esquina */}
              {[
                'left-4 top-4 border-l-2 border-t-2',
                'right-4 top-4 border-r-2 border-t-2',
                'left-4 bottom-4 border-l-2 border-b-2',
                'right-4 bottom-4 border-r-2 border-b-2',
              ].map((c) => (
                <span key={c} className={`absolute h-5 w-5 border-violet-600 ${c}`} />
              ))}

              <p className="label-mono text-violet-700">empezá con un repo</p>

              <h2 className="mx-auto mt-5 max-w-2xl text-balance font-display text-[34px] leading-[1.03] tracking-tightest text-ink-900 sm:text-[50px]">
                Dejá de reportar avance.
                <br />
                <span className="relative inline-block">
                  <span className="italic text-violet-600">Empezá a demostrarlo.</span>
                  <Scribble variant="underline" className="-bottom-1.5 h-4" delay={0.45} />
                </span>
              </h2>

              <p className="mx-auto mt-6 max-w-md text-pretty text-[15px] leading-relaxed text-ink-600">
                Conectá GitHub, elegí un proyecto y mirá cómo los agentes arman el tablero desde tu
                historial real.
              </p>

              <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
                <Button size="lg" onClick={() => onOpenAuth('signup')}>
                  Crear cuenta
                  <ArrowRight className="h-4 w-4" />
                </Button>
                <Button size="lg" variant="paper" onClick={onDemo}>
                  <PlayCircle className="h-4 w-4 text-violet-600" />
                  Ver la demo
                </Button>
              </div>

              <div className="mt-10 flex flex-wrap items-center justify-center gap-x-6 gap-y-2.5">
                {[
                  { i: <GitHubLogo className="h-3.5 w-3.5" />, t: 'Scopes de solo lectura' },
                  { i: <SupabaseLogo className="h-3.5 w-3.5" />, t: 'Datos aislados por proyecto' },
                  { i: null, t: 'Sin tarjeta en el plan inicial' },
                ].map((b) => (
                  <span
                    key={b.t}
                    className="flex items-center gap-1.5 font-mono text-[10.5px] uppercase tracking-wider text-ink-400"
                  >
                    {b.i}
                    {b.t}
                  </span>
                ))}
              </div>
            </div>

            {/* cinta inferior */}
            <div className="border-t-2 border-ink-900 bg-ink-900 py-2.5">
              <Marquee
                reverse
                items={Array.from({ length: 8 }, (_, i) => (
                  <span key={i} className="flex items-center gap-4 px-5">
                    <span className="font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-white">
                      evidencia, no humo
                    </span>
                    <motion.span
                      className="h-2 w-2 rotate-45 bg-mint-500"
                      animate={{ rotate: [45, 135, 45] }}
                      transition={{ duration: 3, repeat: Infinity, delay: i * 0.2 }}
                    />
                  </span>
                ))}
              />
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
