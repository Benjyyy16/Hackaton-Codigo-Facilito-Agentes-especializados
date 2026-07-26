import { useState } from 'react'
import { Navigate, useParams } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Bot,
  GitBranch,
  GitPullRequest,
  KanbanSquare,
  Network,
  Plug,
  RefreshCw,
  Unplug,
  User as UserIcon,
  Users,
} from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { ProjectCanvas } from '@/components/canvas/ProjectCanvas'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Odometer, Stamp } from '@/components/ui/Bits'
import { GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'
import { useAppStore } from '@/store/AppStore'
import type { TaskStatus } from '@/store/types'
import { cn } from '@/lib/cn'

const columns: { id: TaskStatus; label: string; accent: string; head: string }[] = [
  { id: 'backlog', label: 'Backlog', accent: 'bg-ink-300', head: 'bg-paper-200' },
  { id: 'progress', label: 'En curso', accent: 'bg-violet-500', head: 'bg-violet-100' },
  { id: 'review', label: 'Revisión', accent: 'bg-clay-500', head: 'bg-clay-100' },
  { id: 'done', label: 'Hecho', accent: 'bg-mint-500', head: 'bg-mint-100' },
]

export default function ProjectBoard() {
  const { id } = useParams<{ id: string }>()
  const { getProject, collaborators, connectRepo, moveTask } = useAppStore()
  const [view, setView] = useState<'canvas' | 'kanban'>('canvas')
  const [connecting, setConnecting] = useState(false)
  const [dragOver, setDragOver] = useState<TaskStatus | null>(null)

  const project = id ? getProject(id) : undefined
  if (!project) return <Navigate to="/app" replace />

  const people = collaborators.filter((c) => project.collaboratorIds.includes(c.id))
  const done = project.tasks.filter((t) => t.status === 'done').length
  const pct = project.tasks.length ? Math.round((done / project.tasks.length) * 100) : 0

  async function handleConnect() {
    setConnecting(true)
    await new Promise((r) => setTimeout(r, 1100))
    connectRepo(project!.id, `orquesta-demo/${project!.name.toLowerCase().replace(/\s+/g, '-')}`)
    setConnecting(false)
  }

  return (
    <AppShell>
      <div className="px-5 py-7 sm:px-8">
        {/* ================= Cabecera ================= */}
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <span
                className="h-3.5 w-3.5 shrink-0 border-2 border-ink-900"
                style={{ background: `hsl(${project.hue} 62% 60%)` }}
              />
              <h1 className="truncate font-display text-[32px] leading-none tracking-tightest text-ink-900 sm:text-[38px]">
                {project.name}
              </h1>
            </div>
            <p className="mt-2 max-w-xl text-[13.5px] leading-relaxed text-ink-600">
              {project.description}
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {project.repo ? (
                <>
                  <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2.5 py-1 font-mono text-[11px] font-medium text-ink-800">
                    <GitHubLogo className="h-3.5 w-3.5" />
                    {project.repo.fullName}
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2.5 py-1 font-mono text-[11px] font-medium text-ink-800">
                    <GitBranch className="h-3 w-3" />
                    {project.repo.branch}
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded border-2 border-mint-600 bg-mint-100 px-2.5 py-1 font-mono text-[10.5px] font-bold uppercase tracking-wider text-mint-700">
                    <RefreshCw className="h-3 w-3" />
                    sync {project.repo.lastSync}
                  </span>
                </>
              ) : (
                <Button size="sm" variant="mint" loading={connecting} onClick={handleConnect}>
                  <Plug className="h-3.5 w-3.5" />
                  Conectar GitHub
                </Button>
              )}
              {project.database && (
                <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2.5 py-1 font-mono text-[11px] font-medium text-ink-800">
                  <SupabaseLogo className="h-3.5 w-3.5" />
                  {project.database.tables} tablas
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-col items-end gap-3">
            <div className="flex items-center gap-2">
              <div className="flex -space-x-1.5">
                {people.map((c) => (
                  <span key={c.id} className="rounded-full border-2 border-ink-900">
                    <Avatar name={c.name} hue={c.avatarHue} size={28} ring={false} />
                  </span>
                ))}
              </div>
              <span className="flex items-center gap-1 font-mono text-[10.5px] text-ink-400">
                <Users className="h-3 w-3" />
                {people.length}
              </span>
            </div>

            {/* Alternador de vista */}
            <div className="flex items-center gap-1 rounded-lg border-2 border-ink-900 bg-paper p-1 shadow-hard-sm">
              {[
                { id: 'canvas' as const, label: 'Canvas', icon: Network },
                { id: 'kanban' as const, label: 'Kanban', icon: KanbanSquare },
              ].map((v) => (
                <button
                  key={v.id}
                  onClick={() => setView(v.id)}
                  aria-pressed={view === v.id}
                  className={cn(
                    'relative flex items-center gap-1.5 rounded px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider transition-colors',
                    view === v.id ? 'text-white' : 'text-ink-500 hover:text-ink-900',
                  )}
                >
                  {view === v.id && (
                    <motion.span
                      layoutId="view-pill"
                      className="absolute inset-0 rounded bg-violet-600"
                      transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                    />
                  )}
                  <v.icon className="relative h-3.5 w-3.5" />
                  <span className="relative">{v.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ================= Métricas ================= */}
        <div className="mt-6 overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard">
          <div className="grid divide-y-2 divide-ink-100 sm:grid-cols-2 sm:divide-y-0 sm:divide-x-2 lg:grid-cols-4">
            {[
              { label: 'avance verificado', value: `${pct}%`, sub: `${done} de ${project.tasks.length} tareas`, icon: null },
              {
                label: 'prs abiertos',
                value: project.repo ? String(project.repo.stats.openPRs) : '—',
                sub: project.repo ? `${project.repo.stats.mergedPRs} mergeados` : 'sin repo',
                icon: GitPullRequest,
              },
              {
                label: 'cobertura',
                value: project.repo ? `${project.repo.stats.coverage}%` : '—',
                sub: project.repo ? 'según CI' : 'sin repo',
                icon: null,
              },
              {
                label: 'presupuesto',
                value: project.budget.allocated
                  ? `${Math.round((project.budget.spent / project.budget.allocated) * 100)}%`
                  : '—',
                sub: project.budget.allocated
                  ? `$${project.budget.spent.toLocaleString('en-US')} / $${project.budget.allocated.toLocaleString('en-US')}`
                  : 'sin definir',
                icon: null,
              },
            ].map((m, i) => (
              <motion.div
                key={m.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="px-4 py-3.5"
              >
                <p className="label-mono flex items-center gap-1.5 text-ink-400">
                  {m.icon && <m.icon className="h-3 w-3" />}
                  {m.label}
                </p>
                <p className="mt-1 font-display text-[26px] leading-none tracking-tightest text-ink-900">
                  <Odometer value={m.value} />
                </p>
                <p className="mt-1 font-mono text-[10px] text-ink-400">{m.sub}</p>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Aviso sin repo */}
        <AnimatePresence>
          {!project.repo && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden"
            >
              <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border-2 border-clay-500 bg-clay-100 px-4 py-3.5">
                <Unplug className="h-4 w-4 shrink-0 text-clay-700" />
                <p className="flex-1 text-[13px] font-medium text-clay-700">
                  Este tablero no tiene repositorio. Sin él, los agentes no pueden verificar avance
                  ni documentar automáticamente.
                </p>
                <Button size="sm" variant="ink" loading={connecting} onClick={handleConnect}>
                  Conectar ahora
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ================= Vista ================= */}
        <div className="mt-6">
          <AnimatePresence mode="wait">
            {view === 'canvas' ? (
              <motion.div
                key="canvas"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.26 }}
              >
                <ProjectCanvas project={project} onConnectRepo={handleConnect} />
                <p className="mt-2.5 text-center font-mono text-[10.5px] uppercase tracking-wider text-ink-400">
                  arrastrá nodos · uní puertos para crear dependencias · rueda para zoom
                </p>
              </motion.div>
            ) : (
              <motion.div
                key="kanban"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.26 }}
                className="overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard-lg"
              >
                <div className="grid divide-y-2 divide-ink-100 sm:grid-cols-2 sm:divide-y-0 lg:grid-cols-4 lg:divide-x-2">
                  {columns.map((col) => {
                    const items = project.tasks.filter((t) => t.status === col.id)
                    const isOver = dragOver === col.id
                    return (
                      <div
                        key={col.id}
                        onDragOver={(e) => {
                          e.preventDefault()
                          setDragOver(col.id)
                        }}
                        onDragLeave={() => setDragOver(null)}
                        onDrop={(e) => {
                          e.preventDefault()
                          const taskId = e.dataTransfer.getData('text/task-id')
                          if (taskId) moveTask(project.id, taskId, col.id)
                          setDragOver(null)
                        }}
                        className={cn(
                          'min-w-0 transition-colors',
                          isOver && 'bg-violet-50',
                        )}
                      >
                        <div
                          className={cn(
                            'flex items-center justify-between border-b-2 border-ink-100 px-3.5 py-2',
                            col.head,
                          )}
                        >
                          <span className="flex items-center gap-2 font-mono text-[10.5px] font-bold uppercase tracking-[0.13em] text-ink-800">
                            <span className={cn('h-2 w-2 border border-ink-900', col.accent)} />
                            {col.label}
                          </span>
                          <span className="font-mono text-[10.5px] font-bold text-ink-500">
                            {items.length}
                          </span>
                        </div>

                        <div className="flex min-h-[240px] flex-col gap-2 p-3">
                          <AnimatePresence mode="popLayout">
                            {items.map((t) => (
                              <motion.div
                                key={t.id}
                                layout
                                initial={{ opacity: 0, scale: 0.92 }}
                                animate={{ opacity: 1, scale: 1 }}
                                exit={{ opacity: 0, scale: 0.92 }}
                                transition={{ type: 'spring', stiffness: 360, damping: 30 }}
                              >
                                {/* div nativo: Framer consume onDragStart */}
                                <div
                                  draggable
                                  onDragStart={(e) => {
                                    e.dataTransfer.setData('text/task-id', t.id)
                                    e.dataTransfer.effectAllowed = 'move'
                                  }}
                                  className={cn(
                                    'relative cursor-grab rounded-lg border-2 border-ink-900 p-2.5 shadow-hard-sm transition-transform hover:-translate-y-0.5 active:cursor-grabbing',
                                    t.status === 'done' ? 'bg-mint-50' : 'bg-paper',
                                  )}
                                >
                                  <p className="text-[12.5px] font-semibold leading-snug text-ink-900">
                                    {t.title}
                                  </p>
                                  <div className="mt-2 flex items-center justify-between gap-2">
                                    <span className="flex min-w-0 items-center gap-1.5 text-[10px] font-medium text-ink-500">
                                      {t.source === 'agent' ? (
                                        <Bot className="h-2.5 w-2.5 shrink-0 text-violet-600" />
                                      ) : (
                                        <UserIcon className="h-2.5 w-2.5 shrink-0 text-mint-600" />
                                      )}
                                      <span className="truncate">{t.owner}</span>
                                    </span>
                                    {t.ref && (
                                      <span className="shrink-0 rounded border border-ink-200 bg-paper-100 px-1.5 py-0.5 font-mono text-[8.5px] font-medium text-ink-600">
                                        {t.ref}
                                      </span>
                                    )}
                                  </div>
                                  {t.autoSynced && (
                                    <span className="absolute -right-1.5 -top-2">
                                      <Stamp
                                        tone="mint"
                                        className="!border-[1.5px] !px-1 !py-0 !text-[7.5px]"
                                      >
                                        auto
                                      </Stamp>
                                    </span>
                                  )}
                                </div>
                              </motion.div>
                            ))}
                          </AnimatePresence>

                          {items.length === 0 && (
                            <p className="grid flex-1 place-items-center rounded-lg border-2 border-dashed border-ink-200 font-mono text-[10px] uppercase tracking-wider text-ink-300">
                              soltá una tarjeta acá
                            </p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {view === 'kanban' && (
            <p className="mt-2.5 text-center font-mono text-[10.5px] uppercase tracking-wider text-ink-400">
              arrastrá tarjetas entre columnas · con el repo conectado, los merges las mueven solos
            </p>
          )}
        </div>
      </div>
    </AppShell>
  )
}
