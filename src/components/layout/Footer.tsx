import { OrquestaMark, GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'

const columns = [
  { title: 'Producto', links: ['Tablero canvas', 'Agentes', 'Conexiones', 'Reportes'] },
  { title: 'Recursos', links: ['Documentación', 'Changelog', 'Estado', 'Seguridad'] },
  { title: 'Compañía', links: ['Sobre Orquesta', 'Privacidad', 'Términos', 'Contacto'] },
]

export function Footer() {
  return (
    <footer className="relative mt-16 border-t-2 border-ink-900 bg-paper">
      <div className="container-page py-14">
        <div className="grid gap-12 lg:grid-cols-[1.3fr_2fr]">
          <div>
            <div className="flex items-center gap-2.5">
              <OrquestaMark className="h-9 w-9" />
              <span className="text-[17px] font-extrabold tracking-tight text-ink-900">
                Orquesta<span className="text-violet-600">.</span>
              </span>
            </div>
            <p className="mt-4 max-w-sm text-[13.5px] leading-relaxed text-ink-600">
              Multi-agentes de IA que operan como tu CEO técnico. El repositorio manda; el tablero y
              los reportes se derivan de él.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-2">
              {[
                { i: <GitHubLogo className="h-3.5 w-3.5" />, t: 'GitHub' },
                { i: <SupabaseLogo className="h-3.5 w-3.5" />, t: 'Supabase' },
              ].map((b) => (
                <span
                  key={b.t}
                  className="flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-1 font-mono text-[10.5px] font-bold uppercase tracking-wider text-ink-800"
                >
                  {b.i}
                  {b.t}
                </span>
              ))}
            </div>
          </div>

          <div className="grid gap-8 sm:grid-cols-3">
            {columns.map((c) => (
              <div key={c.title}>
                <p className="label-mono border-b-2 border-ink-900 pb-2 text-ink-900">{c.title}</p>
                <ul className="mt-3.5 space-y-2.5">
                  {c.links.map((l) => (
                    <li key={l}>
                      <a
                        href="#"
                        className="group inline-flex items-center gap-1.5 text-[13px] text-ink-600 transition-colors hover:text-violet-700"
                      >
                        <span className="h-1 w-1 bg-ink-200 transition-colors group-hover:bg-violet-600" />
                        {l}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-12 flex flex-col gap-3 border-t-2 border-dashed border-ink-200 pt-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-mono text-[11px] text-ink-400">
            © {new Date().getFullYear()} Orquesta · demo de hackathon
          </p>
          <p className="max-w-md font-mono text-[10px] leading-relaxed text-ink-300">
            GitHub, Supabase, Vercel, Slack, Linear, Notion, Figma y Stripe son marcas de sus
            respectivos propietarios.
          </p>
        </div>
      </div>
    </footer>
  )
}
