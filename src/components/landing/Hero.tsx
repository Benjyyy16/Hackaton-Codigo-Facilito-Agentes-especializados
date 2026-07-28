import { motion, useScroll, useTransform } from 'framer-motion'
import { useRef } from 'react'
import { ArrowRight, GitPullRequest, PlayCircle, TrendingDown } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Marquee, Scribble, Stamp, Typewriter, WordsReveal } from '@/components/ui/Bits'
import { GitHubLogo, SupabaseLogo, SlackLogo, VercelLogo, LinearLogo } from '@/components/brand/Logos'
import { AgentBlueprint } from './AgentBlueprint'

export function Hero({
  onOpenAuth,
  onDemo,
}: {
  onOpenAuth: (mode: 'login' | 'signup') => void
  onDemo: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end start'] })
  const yArt = useTransform(scrollYProgress, [0, 1], [0, 90])
  const fade = useTransform(scrollYProgress, [0, 0.85], [1, 0])

  return (
    <section ref={ref} className="relative overflow-hidden pt-28 sm:pt-32">
      {/* ficha técnica en el margen, como un plano */}
      <div className="pointer-events-none absolute left-3 top-40 hidden xl:block">
        <motion.div
          initial={{ opacity: 0, x: -14 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 1.2, duration: 0.7 }}
          className="label-mono -rotate-90 whitespace-nowrap text-ink-300"
        >
          Datgent / v0.1 / plano general
        </motion.div>
      </div>

      <div className="container-page">
        <div className="grid items-start gap-12 lg:grid-cols-[1.02fr_.98fr] lg:gap-8">
          {/* ============ Columna texto ============ */}
          <div className="pt-4">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="mb-8 inline-flex items-center gap-2 rounded-full border-2 border-ink-900 bg-paper py-1 pl-1.5 pr-3.5 shadow-hard-sm"
            >
              <span className="flex h-5 items-center gap-1 rounded-full bg-mint-500 px-2">
                <motion.span
                  className="h-1.5 w-1.5 rounded-full bg-ink-900"
                  animate={{ opacity: [1, 0.25, 1] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                />
                <span className="font-mono text-[9.5px] font-bold uppercase tracking-wider text-ink-900">
                  live
                </span>
              </span>
              <span className="text-[12px] font-semibold text-ink-700">
                6 agentes leyendo tu repositorio ahora
              </span>
            </motion.div>

            <h1 className="font-display text-[clamp(2.7rem,15vw,4rem)] leading-[0.95] tracking-tightest text-ink-900 lg:text-[72px]">
              <WordsReveal text="Tu CEO técnico" delay={0.08} />
              <br />
              <span className="relative inline-block">
                <WordsReveal text="no duerme," delay={0.3} />
                <Scribble variant="underline" className="-bottom-1 h-3.5" delay={1.1} />
              </span>
              <br />
              <WordsReveal
                text="ni improvisa."
                delay={0.52}
                wordClassName="italic text-violet-600"
              />
            </h1>

            {/* consola con máquina de escribir */}
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.85, duration: 0.6 }}
              className="mt-8 max-w-lg overflow-hidden rounded-lg border-2 border-ink-900 bg-ink-900 shadow-hard"
            >
              <div className="flex items-center gap-1.5 border-b border-white/10 px-3 py-2">
                <span className="h-2 w-2 rounded-full bg-white/25" />
                <span className="h-2 w-2 rounded-full bg-white/25" />
                <span className="h-2 w-2 rounded-full bg-mint-500" />
                <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-white/40">
                  datgent · bitácora
                </span>
              </div>
              <div className="px-3.5 py-3 font-mono text-[12.5px] leading-relaxed text-mint-300">
                <span className="select-none text-white/35">$ </span>
                <Typewriter
                  lines={[
                    'analizando 1284 commits en main…',
                    'PR #214 mergeado → tarjeta movida a Hecho',
                    'costo del sprint: $6.100 · 7 PRs',
                    'docs regeneradas desde el diff real',
                  ]}
                />
              </div>
            </motion.div>

            <motion.p
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1, duration: 0.6 }}
              className="mt-7 max-w-lg text-pretty text-[16px] leading-[1.65] text-ink-600"
            >
              Multi-agentes que planifican, construyen, auditan y reportan. Conectás{' '}
              <span className="inline-flex translate-y-[3px] items-center gap-1 rounded border border-ink-200 bg-paper px-1.5 py-0.5 font-mono text-[13px] font-medium text-ink-900">
                <GitHubLogo className="h-3.5 w-3.5" />
                GitHub
              </span>{' '}
              y{' '}
              <span className="inline-flex translate-y-[3px] items-center gap-1 rounded border border-ink-200 bg-paper px-1.5 py-0.5 font-mono text-[13px] font-medium text-ink-900">
                <SupabaseLogo className="h-3.5 w-3.5" />
                Supabase
              </span>{' '}
              y el tablero se mueve con evidencia del repo. Nada de porcentajes inventados.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.12, duration: 0.6 }}
              className="mt-9 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center"
            >
              <Button size="lg" fullWidth onClick={() => onOpenAuth('login')} className="sm:w-auto">
                Ingresar
                <ArrowRight className="h-4 w-4" />
              </Button>
              <Button size="lg" variant="paper" fullWidth onClick={onDemo} className="sm:w-auto">
                <PlayCircle className="h-4 w-4 text-violet-600" />
                Entrar a la demo
              </Button>
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 1.3 }}
              className="mt-3.5 font-mono text-[11px] text-ink-400"
            >
              La demo abre 3 proyectos reales de ejemplo. Sin registro.
            </motion.p>
          </div>

          {/* ============ Columna plano ============ */}
          <motion.div style={{ y: yArt, opacity: fade }} className="relative mx-auto w-full max-w-[560px] lg:max-w-none">
            <AgentBlueprint />

            {/* recortes flotantes de evidencia */}
            <motion.div
              initial={{ opacity: 0, x: -26, rotate: -8 }}
              animate={{ opacity: 1, x: 0, rotate: -4 }}
              transition={{ delay: 1.45, type: 'spring', stiffness: 200, damping: 16 }}
              className="absolute -left-3 top-4 hidden sm:block"
            >
              <div className="animate-float rounded-lg border-2 border-ink-900 bg-paper px-3 py-2 shadow-hard">
                <div className="flex items-center gap-2">
                  <GitPullRequest className="h-3.5 w-3.5 text-mint-600" />
                  <span className="text-[12px] font-bold text-ink-900">PR #214</span>
                  <Stamp tone="mint" className="!rotate-0 !px-1.5 !py-0 !text-[8.5px]" delay={1.8}>
                    merged
                  </Stamp>
                </div>
                <p className="mt-1 font-mono text-[10px] text-ink-400">tarjeta → Hecho</p>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 26, rotate: 8 }}
              animate={{ opacity: 1, x: 0, rotate: 3 }}
              transition={{ delay: 1.6, type: 'spring', stiffness: 200, damping: 16 }}
              className="absolute -right-2 bottom-16 hidden sm:block"
            >
              <div
                className="rounded-lg border-2 border-ink-900 bg-paper px-3 py-2 shadow-hard"
                style={{ animationDelay: '1.5s' }}
              >
                <div className="flex items-center gap-2">
                  <TrendingDown className="h-3.5 w-3.5 text-violet-600" />
                  <span className="text-[12px] font-bold text-ink-900">Burn −8%</span>
                </div>
                <p className="mt-1 font-mono text-[10px] text-ink-400">vs sprint anterior</p>
              </div>
            </motion.div>
          </motion.div>
        </div>
      </div>

      {/* ============ Cinta de integraciones ============ */}
      <div className="relative mt-16 border-y-2 border-ink-900 bg-ink-900 py-3.5">
        <Marquee
          items={[
            ...[
              { n: 'GitHub', i: <GitHubLogo className="h-4 w-4 text-white" /> },
              { n: 'Supabase', i: <SupabaseLogo className="h-4 w-4" /> },
              { n: 'Vercel', i: <VercelLogo className="h-3.5 w-3.5 text-white" /> },
              { n: 'Slack', i: <SlackLogo className="h-4 w-4" /> },
              { n: 'Linear', i: <LinearLogo className="h-4 w-4 text-white" /> },
            ].flatMap((b) => [
              <span key={b.n} className="flex items-center gap-2 px-6">
                {b.i}
                <span className="font-mono text-[12px] font-medium uppercase tracking-[0.14em] text-white">
                  {b.n}
                </span>
              </span>,
              <span key={`${b.n}-sep`} className="text-mint-500">
                ✳
              </span>,
            ]),
          ]}
        />
      </div>
    </section>
  )
}
