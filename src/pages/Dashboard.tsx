import { memo, useCallback, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  GitPullRequest,
  Plus,
  Unplug,
  Users,
  CloudOff,
  Shield,
  Loader2,
} from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { NewProjectModal } from '@/components/app/NewProjectModal'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Odometer, Stamp } from '@/components/ui/Bits'
import { GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'
import { useAppStore } from '@/store/AppStore'
import { useProjects } from '@/hooks/useProjects'
import { cn } from '@/lib/cn'
import type { Collaborator, Project } from '@/store/types'

/**
 * Tarjeta de proyecto memoizada: mover una tarea en un proyecto ya no
 * re-renderiza las tarjetas de los demás, sólo la afectada.
 */
const ProjectCard = memo(function ProjectCard({
  project,
  people,
  index,
  onAnalyze,
}: {
  project: Project
  people: Collaborator[]
  index: number
  onAnalyze: (repoFullName: string) => void
}) {
  const done = project.tasks.filter((t) => t.status === 'done').length
  const pct = project.tasks.length ? Math.round((done / project.tasks.length) * 100) : 0
  const budgetPct = project.budget.allocated
    ? Math.round((project.budget.spent / project.budget.allocated) * 100)
    : 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.08 + Math.min(index, 8) * 0.07 }}
    >
      <Link
        to={`/app/proyecto/${project.id}`}
        className="group flex h-full flex-col rounded-xl border-2 border-ink-900 bg-paper shadow-hard transition-transform hover:-translate-y-1"
      >
        {/* franja de color del proyecto */}
        <div
          className="h-1.5 rounded-t-[10px]"
          style={{ background: `hsl(${project.hue} 62% 60%)` }}
        />

        <div className="flex flex-1 flex-col p-4 sm:p-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="truncate text-[17px] font-extrabold tracking-tight text-ink-900 sm:text-[18px]">
                {project.name}
              </h2>
              <p className="mt-1.5 line-clamp-2 text-[12.5px] leading-relaxed text-ink-600 sm:text-[13px]">
                {project.description}
              </p>
            </div>
            <ArrowRight
              className="mt-1 h-4 w-4 shrink-0 text-ink-300 transition-all group-hover:translate-x-1 group-hover:text-violet-600"
              aria-hidden
            />
          </div>

          {/* chips de conexión */}
          <div className="mt-4 flex flex-wrap items-center gap-1.5">
            {project.repo ? (
              <span className="inline-flex max-w-full items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                <GitHubLogo className="h-3 w-3 shrink-0" />
                <span className="truncate">{project.repo.fullName}</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded border-2 border-clay-500 bg-clay-100 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-clay-700">
                <Unplug className="h-3 w-3" aria-hidden />
                sin repo
              </span>
            )}
            {project.database && (
              <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                <SupabaseLogo className="h-3 w-3" />
                {project.database.tables} tablas
              </span>
            )}
            {project.repo && (
              <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                <GitPullRequest className="h-3 w-3" aria-hidden />
                {project.repo.stats.openPRs} PRs
              </span>
            )}
          </div>

          {/* progreso segmentado */}
          <div className="mt-5 flex-1 space-y-4">
            <div>
              <div className="mb-1.5 flex flex-wrap items-center justify-between gap-1">
                <span className="label-mono text-ink-400">avance verificado</span>
                <span className="font-mono text-[11px] font-bold text-ink-900">
                  {done}/{project.tasks.length} · {pct}%
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

            {project.budget.allocated > 0 && (
              <div>
                <div className="mb-1.5 flex flex-wrap items-center justify-between gap-1">
                  <span className="label-mono text-ink-400">presupuesto</span>
                  <span
                    className={cn(
                      'font-mono text-[11px] font-bold tabular-nums',
                      budgetPct > 85 ? 'text-clay-700' : 'text-ink-900',
                    )}
                  >
                    ${project.budget.spent.toLocaleString('en-US')} / $
                    {project.budget.allocated.toLocaleString('en-US')}
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
          <div className="mt-5 flex items-center justify-between gap-2 border-t-2 border-dashed border-ink-200 pt-4">
            <div className="flex min-w-0 items-center gap-2">
              <div className="flex -space-x-1.5">
                {people.slice(0, 4).map((c) => (
                  <span key={c.id} className="rounded-full border-2 border-ink-900">
                    <Avatar name={c.name} hue={c.avatarHue} size={24} ring={false} />
                  </span>
                ))}
              </div>
              <span className="flex items-center gap-1 font-mono text-[10.5px] text-ink-400">
                <Users className="h-3 w-3" aria-hidden />
                {people.length}
              </span>
            </div>
            {project.repo && (
              <span className="shrink-0 font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
                sync {project.repo.lastSync}
              </span>
            )}
          </div>

          {/* Botón analizar */}
          {project.repo && (
            <button
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onAnalyze(project.repo!.fullName)
              }}
              aria-label={`Analizar riesgos de ${project.repo.fullName}`}
              className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg border-2 border-violet-600 bg-violet-50 px-3 py-2 font-mono text-[11px] font-bold uppercase tracking-wider text-violet-700 transition-all hover:bg-violet-600 hover:text-white"
            >
              <Shield className="h-3.5 w-3.5" aria-hidden />
              Analizar riesgos
            </button>
          )}
        </div>
      </Link>
    </motion.div>
  )
})

export default function Dashboard() {
  const { projects, collaborators, user } = useAppStore()
  const { projects: apiProjects, loading: apiLoading, error: apiError } = useProjects()
  const [modalOpen, setModalOpen] = useState(false)
  const navigate = useNavigate()

  const usingApi = !apiError && !apiLoading && apiProjects.length > 0

  const stats = useMemo(() => {
    const totalTasks = projects.reduce((s, p) => s + p.tasks.length, 0)
    const doneTasks = projects.reduce(
      (s, p) => s + p.tasks.filter((t) => t.status === 'done').length,
      0,
    )
    const connected = projects.filter((p) => p.repo).length
    return [
      { label: 'proyectos', value: String(projects.length), icon: null },
      { label: 'repos conectados', value: `${connected}/${projects.length}`, icon: 'gh' },
      { label: 'tareas cerradas', value: `${doneTasks}/${totalTasks}`, icon: null },
      { label: 'colaboradores', value: String(collaborators.length), icon: null },
    ]
  }, [projects, collaborators.length])

  /** Colaboradores por proyecto: se calcula una vez, no por tarjeta y por render. */
  const peopleByProject = useMemo(() => {
    const map = new Map<string, Collaborator[]>()
    for (const p of projects) {
      map.set(
        p.id,
        collaborators.filter((c) => p.collaboratorIds.includes(c.id)),
      )
    }
    return map
  }, [projects, collaborators])

  const handleAnalyze = useCallback(
    (repoFullName: string) => {
      navigate(`/app/datgent?repo=${encodeURIComponent(repoFullName)}`)
    },
    [navigate],
  )

  const openModal = useCallback(() => setModalOpen(true), [])
  const closeModal = useCallback(() => setModalOpen(false), [])

  return (
    <AppShell onNewProject={openModal}>
      <div className="mx-auto w-full max-w-6xl px-4 py-7 sm:px-8 sm:py-12">
        {/* Encabezado */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="label-mono text-ink-400">
              {user ? `sesión · ${user.name.split(' ')[0]}` : 'bienvenido'}
            </p>
            <h1 className="mt-2 font-display text-[32px] leading-none tracking-tightest text-ink-900 sm:text-[46px]">
              Tus tableros
            </h1>
          </div>
          <Button onClick={openModal} aria-label="Crear nuevo proyecto">
            <Plus className="h-4 w-4" aria-hidden />
            Nuevo proyecto
          </Button>
        </div>

        {/* Estado de la API */}
        {apiLoading && (
          <div
            className="mt-4 flex items-center gap-2 rounded-lg border-2 border-ink-200 bg-paper px-3 py-2"
            role="status"
            aria-live="polite"
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-600" aria-hidden />
            <p className="text-xs text-ink-500">Sincronizando proyectos con el backend…</p>
          </div>
        )}
        {usingApi && (
          <div className="mt-4 rounded-lg border-2 border-mint-500 bg-mint-50 px-3 py-2">
            <p className="text-xs text-mint-700">
              ✓ Conectado a API — {apiProjects.length} proyecto(s) en backend
            </p>
          </div>
        )}
        {apiError && !apiLoading && (
          <div className="mt-4 flex items-start gap-2 rounded-lg border-2 border-ink-200 bg-paper px-3 py-2">
            <CloudOff className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-400" aria-hidden />
            <p className="text-xs text-ink-500">API no disponible — mostrando datos locales</p>
          </div>
        )}

        {/* Panel de resumen: ledger de 4 celdas */}
        <div className="mt-8 overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard">
          <div className="grid grid-cols-2 divide-x-2 divide-y-2 divide-ink-100 sm:grid-cols-4 sm:divide-y-0">
            {stats.map((s, i) => (
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
                <p className="mt-1.5 font-display text-[26px] leading-none tracking-tightest text-ink-900 sm:text-[30px]">
                  <Odometer value={s.value} />
                </p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Proyectos */}
        <div className="mt-8 grid gap-4 sm:mt-10 sm:gap-5 lg:grid-cols-2">
          {projects.map((p, i) => (
            <ProjectCard
              key={p.id}
              project={p}
              people={peopleByProject.get(p.id) ?? []}
              index={i}
              onAnalyze={handleAnalyze}
            />
          ))}

          {/* Crear */}
          <motion.button
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + Math.min(projects.length, 8) * 0.07 }}
            onClick={openModal}
            className="group flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-ink-300 bg-paper/60 p-6 transition-colors hover:border-violet-600 hover:bg-violet-50 sm:min-h-[240px]"
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
        onClose={closeModal}
        onCreated={(id) => {
          setModalOpen(false)
          navigate(`/app/proyecto/${id}`)
        }}
      />
    </AppShell>
  )
}
