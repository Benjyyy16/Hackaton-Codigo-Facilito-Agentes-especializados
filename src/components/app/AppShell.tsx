import { type ReactNode } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Brain, LayoutGrid, LogOut, Plus, UserCircle2, Zap } from 'lucide-react'
import { OrquestaMark, GitHubLogo } from '@/components/brand/Logos'
import { Avatar } from '@/components/ui/Avatar'
import { useAppStore } from '@/store/AppStore'
import { cn } from '@/lib/cn'

export function AppShell({
  children,
  onNewProject,
}: {
  children: ReactNode
  onNewProject?: () => void
}) {
  const { user, projects, signOut } = useAppStore()
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen">
      {/* ================= Sidebar ================= */}
      <aside className="sticky top-0 hidden h-screen w-[266px] shrink-0 flex-col border-r-2 border-ink-900 bg-paper lg:flex">
        <div className="flex h-[66px] items-center border-b-2 border-ink-900 px-5">
          <Link to="/" className="flex items-center gap-2.5">
            <OrquestaMark className="h-8 w-8" />
            <span className="text-[16px] font-extrabold tracking-tight text-ink-900">
              Datgent<span className="text-violet-600">.</span>
            </span>
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto p-3">
          <NavLink
            to="/app"
            end
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 rounded-lg border-2 px-3 py-2.5 text-[13.5px] font-bold transition-all',
                isActive
                  ? 'border-ink-900 bg-violet-600 text-white shadow-hard-sm'
                  : 'border-transparent text-ink-600 hover:border-ink-900 hover:bg-paper-100',
              )
            }
          >
            <LayoutGrid className="h-4 w-4" />
            Todos los tableros
          </NavLink>

          <NavLink
            to="/app/datgent"
            className={({ isActive }) =>
              cn(
                'mt-1.5 flex items-center gap-2.5 rounded-lg border-2 px-3 py-2.5 text-[13.5px] font-bold transition-all',
                isActive
                  ? 'border-ink-900 bg-violet-600 text-white shadow-hard-sm'
                  : 'border-transparent text-ink-600 hover:border-ink-900 hover:bg-paper-100',
              )
            }
          >
            <Brain className="h-4 w-4" />
            Datgent
          </NavLink>

          <div className="mt-7 flex items-center justify-between border-b-2 border-ink-900 pb-2">
            <p className="label-mono text-ink-900">proyectos · {projects.length}</p>
            {onNewProject && (
              <button
                onClick={onNewProject}
                aria-label="Nuevo proyecto"
                className="grid h-5 w-5 place-items-center rounded border-2 border-ink-900 bg-paper text-ink-900 transition hover:bg-violet-600 hover:text-white"
              >
                <Plus className="h-3 w-3" />
              </button>
            )}
          </div>

          <div className="mt-2.5 space-y-1.5">
            {projects.map((p) => (
              <NavLink
                key={p.id}
                to={`/app/proyecto/${p.id}`}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center gap-2.5 rounded-lg border-2 px-3 py-2.5 transition-all',
                    isActive
                      ? 'border-ink-900 bg-paper-100 shadow-hard-sm'
                      : 'border-ink-100 hover:border-ink-900',
                  )
                }
              >
                <span
                  className="h-2.5 w-2.5 shrink-0 border-2 border-ink-900"
                  style={{ background: `hsl(${p.hue} 62% 60%)` }}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-bold text-ink-900">
                    {p.name}
                  </span>
                  <span className="mt-0.5 flex items-center gap-1 truncate font-mono text-[9.5px] text-ink-400">
                    {p.repo ? (
                      <>
                        <GitHubLogo className="h-2.5 w-2.5 shrink-0" />
                        {p.repo.fullName.split('/')[1]}
                      </>
                    ) : (
                      'sin repo'
                    )}
                  </span>
                </span>
                {!p.repo && (
                  <span
                    className="h-2 w-2 shrink-0 rotate-45 border border-ink-900 bg-clay-500"
                    title="Repo sin conectar"
                  />
                )}
              </NavLink>
            ))}
          </div>
        </nav>

        {/* Usuario */}
        {user && (
          <div className="border-t-2 border-ink-900 p-3">
            {user.isDemo && (
              <div className="mb-2.5 flex items-center gap-2 rounded-lg border-2 border-violet-600 bg-violet-50 px-2.5 py-1.5">
                <Zap className="h-3 w-3 shrink-0 text-violet-600" />
                <span className="font-mono text-[9.5px] font-bold uppercase tracking-wider text-violet-700">
                  sesión demo
                </span>
              </div>
            )}
            <Link
              to="/perfil"
              className="flex items-center gap-3 rounded-lg border-2 border-ink-100 px-2.5 py-2.5 transition-colors hover:border-ink-900"
            >
              <Avatar name={user.name} hue={user.avatarHue} size={34} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-bold text-ink-900">
                  {user.name}
                </span>
                <span className="block truncate text-[10.5px] text-ink-500">{user.title}</span>
              </span>
              <UserCircle2 className="h-4 w-4 shrink-0 text-ink-300" />
            </Link>
            <button
              onClick={() => {
                signOut()
                navigate('/')
              }}
              className="mt-1.5 flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[12.5px] font-medium text-ink-500 transition hover:bg-rose-50 hover:text-rose-600"
            >
              <LogOut className="h-3.5 w-3.5" />
              Cerrar sesión
            </button>
          </div>
        )}
      </aside>

      {/* ================= Contenido ================= */}
      <div className="min-w-0 flex-1">
        {/* barra móvil */}
        <div className="sticky top-0 z-40 border-b-2 border-ink-900 bg-paper/95 backdrop-blur-md lg:hidden">
          <div className="flex h-[58px] items-center justify-between px-4">
            <Link to="/app" className="flex items-center gap-2">
              <OrquestaMark className="h-7 w-7" />
              <span className="text-[14.5px] font-extrabold text-ink-900">Datgent</span>
            </Link>
            <div className="flex items-center gap-2">
              {user?.isDemo && (
                <span className="rounded border-2 border-violet-600 bg-violet-50 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase text-violet-700">
                  demo
                </span>
              )}
              {user && (
                <Link to="/perfil" aria-label="Ver perfil" className="rounded-full border-2 border-ink-900">
                  <Avatar name={user.name} hue={user.avatarHue} size={28} ring={false} />
                </Link>
              )}
              {onNewProject && (
                <button
                  onClick={onNewProject}
                  aria-label="Nuevo proyecto"
                  className="grid h-7 w-7 place-items-center rounded border-2 border-ink-900 bg-paper text-ink-900"
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden />
                </button>
              )}
            </div>
          </div>

          {/* Navegación principal en móvil: el sidebar está oculto en este breakpoint */}
          <nav className="flex items-center gap-1.5 overflow-x-auto px-4 pb-2" aria-label="Secciones">
            <NavLink
              to="/app"
              end
              className={({ isActive }) =>
                cn(
                  'flex shrink-0 items-center gap-1.5 rounded-lg border-2 px-2.5 py-1.5 font-mono text-[10.5px] font-bold uppercase tracking-wider transition-colors',
                  isActive
                    ? 'border-ink-900 bg-violet-600 text-white'
                    : 'border-ink-200 text-ink-600',
                )
              }
            >
              <LayoutGrid className="h-3.5 w-3.5" aria-hidden />
              Tableros
            </NavLink>
            <NavLink
              to="/app/datgent"
              className={({ isActive }) =>
                cn(
                  'flex shrink-0 items-center gap-1.5 rounded-lg border-2 px-2.5 py-1.5 font-mono text-[10.5px] font-bold uppercase tracking-wider transition-colors',
                  isActive
                    ? 'border-ink-900 bg-violet-600 text-white'
                    : 'border-ink-200 text-ink-600',
                )
              }
            >
              <Brain className="h-3.5 w-3.5" aria-hidden />
              Datgent
            </NavLink>
          </nav>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          {children}
        </motion.div>
      </div>
    </div>
  )
}
