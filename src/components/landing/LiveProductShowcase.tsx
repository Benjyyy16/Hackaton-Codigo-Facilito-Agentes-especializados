import { ArrowRight, Bot, PlugZap, SendHorizonal } from 'lucide-react'
import { CodigoFacilitoLogo, GitHubLogo, KiroLogo, OrquestaMark, VercelLogo } from '@/components/brand/Logos'

const agents = [
  ['Agente Jira', '90', '4 hallazgos · confianza 94%', 'crítico'],
  ['Agente Código', '85', '7 hallazgos · confianza 95%', 'crítico'],
  ['Agente Finanzas', '100', '3 hallazgos · confianza 81%', 'crítico'],
  ['Agente Datos', '75', '1 hallazgo · confianza 100%', 'alto'],
]

const integrations = [
  ['GitHub', 'Repos, PRs, issues', <GitHubLogo className="h-5 w-5" />],
  ['Jira', 'Issues, sprints', <span className="text-xl">📋</span>],
  ['Vercel', 'Deploys, logs', <VercelLogo className="h-4 w-4 text-ink-900" />],
  ['Slack', 'Alertas', <span className="text-xl">💬</span>],
]

export function LiveProductShowcase() {
  return (
    <section className="relative py-16 sm:py-24">
      <div className="container-page">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="label-mono text-violet-600">producto real</p>
            <h2 className="font-display text-[32px] leading-none text-ink-900 sm:text-[44px]">
              Datgent Cerebro en vivo
            </h2>
          </div>
          <div className="flex items-center gap-2 rounded-xl border-2 border-ink-900 bg-paper px-3 py-2 shadow-hard-sm">
            <OrquestaMark className="h-8 w-8" />
            <CodigoFacilitoLogo className="h-8 w-8" />
            <KiroLogo className="h-8 w-8" />
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.1fr_.9fr]">
          <div className="rounded-xl border-2 border-ink-900 bg-paper shadow-hard-lg">
            <div className="flex items-center justify-between border-b-2 border-ink-100 bg-violet-50 px-5 py-3">
              <span className="flex items-center gap-2 text-[15px] font-extrabold text-ink-900">
                <Bot className="h-4 w-4 text-violet-600" />
                Datgent Cerebro
                <span className="label-mono text-ink-400">núcleo multiagente</span>
              </span>
              <span className="rounded-full border border-mint-500 bg-mint-100 px-3 py-1 font-mono text-[10px] font-bold text-mint-700">
                en vivo
              </span>
            </div>
            <div className="min-h-[270px] p-5">
              <div className="max-w-3xl rounded-xl bg-ink-100 px-4 py-3">
                <p className="label-mono text-violet-600">Datgent Cerebro</p>
                <p className="mt-2 text-[15px] leading-relaxed text-ink-800">
                  Hola, soy Datgent Cerebro. Coordino agentes especializados para detectar riesgos,
                  compromisos en peligro e impacto financiero antes de que afecten tus proyectos.
                </p>
              </div>
            </div>
            <div className="flex gap-2 border-t-2 border-ink-100 p-4">
              <input
                className="min-w-0 flex-1 rounded-lg border-2 border-violet-600 bg-paper px-3 py-2 text-[14px] outline-none"
                value="hola"
                readOnly
                aria-label="Mensaje de ejemplo"
              />
              <button className="grid h-11 w-11 place-items-center rounded-lg border-2 border-ink-900 bg-violet-600 text-white shadow-hard-sm">
                <SendHorizonal className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="space-y-5">
            <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
              <h3 className="flex items-center gap-2 text-[20px] font-extrabold text-ink-900">
                <PlugZap className="h-5 w-5 text-violet-600" />
                Integraciones
              </h3>
              <div className="mt-4 space-y-3">
                {integrations.map(([name, desc, icon]) => (
                  <div key={String(name)} className="flex items-center justify-between rounded-lg border-2 border-mint-500 bg-mint-50 px-4 py-3">
                    <span className="flex items-center gap-3">
                      {icon}
                      <span>
                        <span className="font-extrabold text-ink-900">{name}</span>
                        <span className="ml-2 text-[13px] text-ink-500">{desc}</span>
                      </span>
                    </span>
                    <span className="rounded-full border border-mint-500 bg-mint-100 px-2 py-0.5 font-mono text-[10px] font-bold text-mint-700">✓ ON</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
              <p className="label-mono text-ink-400">resumen</p>
              {[
                ['Proyectos', '3'],
                ['Tareas cerradas', '3/15'],
                ['Repos conectados', '2'],
                ['Colaboradores', '5'],
              ].map(([k, v]) => (
                <p key={k} className="mt-3 flex justify-between text-[15px] text-ink-600">
                  <span>{k}</span>
                  <span className="font-display text-[24px] leading-none text-ink-900">{v}</span>
                </p>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {agents.map(([name, score, meta, sev]) => (
            <article key={name} className="rounded-xl border-2 border-ink-900 bg-paper p-4 shadow-hard-sm transition-transform hover:-translate-y-1">
              <div className="flex items-start justify-between">
                <h3 className="text-[16px] font-extrabold text-ink-900">{name}</h3>
                <span className="rounded-full border border-clay-400 bg-clay-50 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-clay-700">{sev}</span>
              </div>
              <p className="mt-3 font-display text-[34px] leading-none text-ink-900">
                {score}<span className="text-[14px] text-ink-300">/100</span>
              </p>
              <p className="mt-3 font-mono text-[11px] text-ink-500">{meta}</p>
              <button className="mt-4 flex items-center gap-1 font-mono text-[10px] font-bold uppercase tracking-wider text-violet-700">
                Ver evidencia <ArrowRight className="h-3 w-3" />
              </button>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}
