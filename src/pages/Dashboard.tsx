import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, GitPullRequest, Plus, Unplug, Users, CloudOff } from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { NewProjectModal } from '@/components/app/NewProjectModal'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Odometer, Stamp } from '@/components/ui/Bits'
import { GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'
import { useAppStore } from '@/store/AppStore'
import { useProjects } from '@/hooks/useProjects'
import { cn } from '@/lib/cn'

export default function Dashboard() {
  const { projects, collaborators, user } = useAppStore()
  const { projects: apiProjects, loading: apiLoading, error: apiError } = useProjects()
  const [modalOpen, setModalOpen] = useState(false)
  const navigate = useNavigate()

  // Banner sutil si API no disponible
  const usingApi = !apiError && !apiLoading && apiProjects.length > 0

  const totalTasks = projects.reduce((s, p) => s + p.tasks.length, 0)
  const doneTasks = projects.reduce(
    (s, p) => s + p.tasks.filter((t) => t.status === 'done').length,
    0,
  )
  const connected = projects.filter((p) => p.repo).length

  return (
    <AppShell onNewProject={() => setModalOpen(true)}>
      <div className="mx-auto w-full max-w-6xl px-5 py-9 sm:px-8 sm:py-12">
        {/* Encabezado */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="label-mono text-ink-400">
              {user ? `sesión · ${user.name.split(' ')[0]}` : 'bienvenido'}
            </p>
            <h1 className="mt-2 font-display text-[38px] leading-none tracking-tightest text-ink-900 sm:text-[46px]">
              Tus tableros
            </h1>
          </div>
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="h-4 w-4" />
            Nuevo proyecto
          </Button>
        </div>

        {/* Panel de resumen: ledger de 4 celdas */}
        {usingApi && (
          <div className="mt-4 rounded-lg border border-mint-600/30 bg-mint-900/10 px-3 py-2">
            <p className="text-xs text-mint-400">
              ✓ Conectado a API — {apiProjects.length} proyecto(s) en backend
            </p>
          </div>
        )}
        {apiError && (
          <div className="mt-4 flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-800/50 px-3 py-2">
            <CloudOff className="h-3.5 w-3.5 text-ink-400" />
            <p className="text-xs text-ink-400">API no disponible — mostrando datos locales</p>
          </div>
        )}
        <div className="mt-8 overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard">
          <div className="grid divide-y-2 divide-ink-100 sm:grid-cols-4 sm:divide-y-0 sm:divide-x-2">
            {[
              { label: 'proyectos', value: String(projects.length), icon: null },
              { label: 'repos conectados', value: `${connected}/${projects.length}`, icon: 'gh' },
              { label: 'tareas cerradas', value: `${doneTasks}/${totalTasks}`, icon: null },
              { label: 'colaboradores', value: String(collaborators.length), icon: null },
            ].map((s, i) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="p-4"
              >
                <p className="label-mono flex items-center gap-1.5 text-ink-400">
                  {s.icon === 'gh' && <GitHubLogo className="h-3 w-3" />}
                  {s.label}
                </p>
                <p className="mt-1.5 font-display text-[30px] leading-none tracking-tightest text-ink-900">
                  <Odometer value={s.value} />
                </p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Proyectos */}
        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          {projects.map((p, i) => {
            const done = p.tasks.filter((t) => t.status === 'done').length
            const pct = p.tasks.length ? Math.round((done / p.tasks.length) * 100) : 0
            const people = collaborators.filter((c) => p.collaboratorIds.includes(c.id))
            const budgetPct = p.budget.allocated
              ? Math.round((p.budget.spent / p.budget.allocated) * 100)
              : 0

            return (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 + i * 0.07 }}
              >
                <Link
                  to={`/app/proyecto/${p.id}`}
                  className="group flex h-full flex-col rounded-xl border-2 border-ink-900 bg-paper shadow-hard transition-transform hover:-translate-y-1"
                >
                  {/* franja de color del proyecto */}
                  <div
                    className="h-1.5 rounded-t-[10px]"
                    style={{ background: `hsl(${p.hue} 62% 60%)` }}
                  />

                  <div className="flex flex-1 flex-col p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="truncate text-[18px] font-extrabold tracking-tight text-ink-900">
                          {p.name}
                        </h2>
                        <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-ink-600">
                          {p.description}
                        </p>
                      </div>
                      <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-ink-300 transition-all group-hover:translate-x-1 group-hover:text-violet-600" />
                    </div>

                    {/* chips de conexión */}
                    <div className="mt-4 flex flex-wrap items-center gap-1.5">
                      {p.repo ? (
                        <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                          <GitHubLogo className="h-3 w-3" />
                          {p.repo.fullName}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded border-2 border-clay-500 bg-clay-100 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-clay-700">
                          <Unplug className="h-3 w-3" />
                          sin repo
                        </span>
                      )}
                      {p.database && (
                        <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                          <SupabaseLogo className="h-3 w-3" />
                          {p.database.tables} tablas
                        </span>
                      )}
                      {p.repo && (
                        <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                          <GitPullRequest className="h-3 w-3" />
                          {p.repo.stats.openPRs} PRs
                        </span>
                      )}
                    </div>

                    {/* progreso segmentado */}
                    <div className="mt-5 flex-1 space-y-4">
                      <div>
                        <div className="mb-1.5 flex items-center justify-between">
                          <span className="label-mono text-ink-400">avance verificado</span>
                          <span className="font-mono text-[11px] font-bold text-ink-900">
                            {done}/{p.tasks.length} · {pct}%
                          </span>
                        </div>
                        <div className="flex h-2.5 gap-[2px] rounded border-2 border-ink-900 bg-paper p-[2px]">
                          {Array.from({ length: 16 }, (_, k) => (
                            <motion.span
                              key={k}
                              className={cn(
                                'flex-1',
                                k < Math.round((pct / 100) * 16) ? 'bg-mint-500' : 'bg-ink-100',
                              )}
                              initial={{ scaleY: 0 }}
                              animate={{ scaleY: 1 }}
                              transition={{ delay: 0.3 + k * 0.02 }}
                            />
                          ))}
                        </div>
                      </div>

                      {p.budget.allocated > 0 && (
                        <div>
                          <div className="mb-1.5 flex items-center justify-between">
                            <span className="label-mono text-ink-400">presupuesto</span>
                            <span
                              className={cn(
                                'font-mono text-[11px] font-bold tabular-nums',
                                budgetPct > 85 ? 'text-clay-700' : 'text-ink-900',
                              )}
                            >
                              ${p.budget.spent.toLocaleString('en-US')} / $
                              {p.budget.allocated.toLocaleString('en-US')}
                            </span>
                          </div>
                          <div className="flex h-2.5 gap-[2px] rounded border-2 border-ink-900 bg-paper p-[2px]">
                            {Array.from({ length: 16 }, (_, k) => (
                              <motion.span
                                key={k}
                                className={cn(
                                  'flex-1',
                                  k < Math.round((budgetPct / 100) * 16)
                                    ? budgetPct > 85
                                      ? 'bg-clay-500'
                                      : 'bg-violet-600'
                                    : 'bg-ink-100',
                                )}
                                initial={{ scaleY: 0 }}
                                animate={{ scaleY: 1 }}
                                transition={{ delay: 0.4 + k * 0.02 }}
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* pie */}
                    <div className="mt-5 flex items-center justify-between border-t-2 border-dashed border-ink-200 pt-4">
                      <div className="flex items-center gap-2">
                        <div className="flex -space-x-1.5">
                          {people.slice(0, 4).map((c) => (
                            <span key={c.id} className="rounded-full border-2 border-ink-900">
                              <Avatar name={c.name} hue={c.avatarHue} size={24} ring={false} />
                            </span>
                          ))}
                        </div>
                        <span className="flex items-center gap-1 font-mono text-[10.5px] text-ink-400">
                          <Users className="h-3 w-3" />
                          {people.length}
                        </span>
                      </div>
                      {p.repo && (
                        <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
                          sync {p.repo.lastSync}
                        </span>
                      )}
                    </div>
                  </div>
                </Link>
              </motion.div>
            )
          })}

          {/* Crear */}
          <motion.button
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + projects.length * 0.07 }}
            onClick={() => setModalOpen(true)}
            className="group flex min-h-[240px] flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-ink-300 bg-paper/60 p-6 transition-colors hover:border-violet-600 hover:bg-violet-50"
          >
            <span className="grid h-12 w-12 place-items-center rounded-lg border-2 border-ink-900 bg-paper transition-all group-hover:-rotate-12 group-hover:bg-violet-600">
              <Plus className="h-5 w-5 text-ink-900 transition-colors group-hover:text-white" />
            </span>
            <span className="text-center">
              <span className="block text-[14.5px] font-bold text-ink-900">Nuevo proyecto</span>
              <span className="mt-0.5 block font-mono text-[10.5px] uppercase tracking-wider text-ink-400">
                tablero + repo
              </span>
            </span>
          </motion.button>
        </div>

        {user?.isDemo && (
          <div className="mt-10 flex justify-center">
            <Stamp tone="violet">datos de demostración</Stamp>
          </div>
        )}
      </div>

      <NewProjectModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={(id) => {
          setModalOpen(false)
          navigate(`/app/proyecto/${id}`)
        }}
      />
    </AppShell>
  )
}
