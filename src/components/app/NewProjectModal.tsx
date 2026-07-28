import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, FolderPlus, Loader2, X, Zap } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { GitHubLogo } from '@/components/brand/Logos'
import { useAppStore } from '@/store/AppStore'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { cn } from '@/lib/cn'
import { listUserRepos, type GitHubRepo } from '@/lib/githubApi'

/** Repos que devolvería la API de GitHub tras el OAuth. */
const availableRepos = [
  { full: 'nebula-labs/design-system', lang: 'TypeScript', priv: false },
  { full: 'nebula-labs/api-gateway', lang: 'Go', priv: true },
  { full: 'orion/mobile-client', lang: 'Swift', priv: true },
  { full: 'atlas-data/etl-jobs', lang: 'Python', priv: false },
]

export function NewProjectModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (id: string) => void
}) {
  const { createProject, user } = useAppStore()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [repo, setRepo] = useState<string | null>(null)
  const [repos, setRepos] = useState(availableRepos)
  const [reposLoading, setReposLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  /** Mantiene el foco dentro del modal y lo devuelve al cerrar. */
  const dialogRef = useFocusTrap<HTMLDivElement>(open)

  useEffect(() => {
    if (!open) {
      setName('')
      setDescription('')
      setRepo(null)
      setLoading(false)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    if (!open || !user || user.isDemo) {
      setRepos(availableRepos)
      return
    }
    const controller = new AbortController()
    setReposLoading(true)
    listUserRepos(controller.signal)
      .then((data: GitHubRepo[]) => {
        if (controller.signal.aborted) return
        setRepos(
          data.map((r) => ({
            full: r.full_name,
            lang: r.language ?? r.default_branch,
            priv: r.private,
          })),
        )
      })
      .catch(() => setRepos([]))
      .finally(() => {
        if (!controller.signal.aborted) setReposLoading(false)
      })
    return () => controller.abort()
  }, [open, user])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (name.trim().length < 2) return
    setLoading(true)
    await new Promise((r) => setTimeout(r, 700))
    const p = createProject({
      name: name.trim(),
      description: description.trim() || 'Sin descripción todavía.',
      repoFullName: repo ?? undefined,
    })
    setLoading(false)
    onCreated(p.id)
  }

  async function createExample() {
    setLoading(true)
    await new Promise((r) => setTimeout(r, 350))
    const p = createProject({
      name: 'Repo de prueba Datgent',
      description: 'Tablero sandbox para probar agentes, kanban, canvas y chat IA.',
      repoFullName: 'Benjyyy16/datgent-prueba',
    })
    setLoading(false)
    onCreated(p.id)
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <motion.button
            aria-label="Cerrar"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 cursor-default bg-ink-900/45 backdrop-blur-sm"
          />
          <motion.div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="np-title"
            initial={{ opacity: 0, y: 26, scale: 0.97, rotate: -1 }}
            animate={{ opacity: 1, y: 0, scale: 1, rotate: 0 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: 'spring', stiffness: 300, damping: 27 }}
            className="relative z-10 max-h-[92vh] w-full max-w-[500px] overflow-y-auto rounded-2xl border-2 border-ink-900 bg-paper shadow-hard-lg"
          >
            <div className="h-2 bg-hatch bg-[length:9px_9px]" />

            <button
              onClick={onClose}
              aria-label="Cerrar"
              className="absolute right-3.5 top-5 grid h-8 w-8 place-items-center rounded-lg border-2 border-ink-900 bg-paper text-ink-900 transition hover:bg-violet-100"
            >
              <X className="h-3.5 w-3.5" />
            </button>

            <div className="px-6 pb-7 pt-6 sm:px-8">
              <div className="flex items-center gap-3">
                <span className="grid h-11 w-11 place-items-center rounded-lg border-2 border-ink-900 bg-violet-600 shadow-hard-sm">
                  <FolderPlus className="h-5 w-5 text-white" />
                </span>
                <div>
                  <h2
                    id="np-title"
                    className="font-display text-[23px] leading-none tracking-tightest text-ink-900"
                  >
                    Nuevo proyecto
                  </h2>
                  <p className="mt-1 text-[12.5px] text-ink-500">
                    Cada proyecto tiene su tablero y su repo.
                  </p>
                </div>
              </div>

              <form onSubmit={submit} className="mt-6 space-y-4">
                <div>
                  <label htmlFor="np-name" className="label-mono mb-1.5 block text-ink-500">
                    Nombre del proyecto
                  </label>
                  <input
                    id="np-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Nébula Checkout"
                    className="h-11 w-full rounded-[10px] border-2 border-ink-900 bg-paper px-3.5 text-[14px] text-ink-900 placeholder:text-ink-300 transition focus:border-violet-600 focus:outline-none"
                  />
                </div>

                <div>
                  <label htmlFor="np-desc" className="label-mono mb-1.5 block text-ink-500">
                    Descripción
                  </label>
                  <textarea
                    id="np-desc"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={2}
                    placeholder="¿Qué construye este proyecto?"
                    className="w-full resize-none rounded-[10px] border-2 border-ink-900 bg-paper px-3.5 py-2.5 text-[14px] text-ink-900 placeholder:text-ink-300 transition focus:border-violet-600 focus:outline-none"
                  />
                </div>

                <div>
                  <p className="label-mono mb-2 flex items-center gap-1.5 text-ink-500">
                    <GitHubLogo className="h-3.5 w-3.5" />
                    tus repositorios
                  </p>
                  <button
                    type="button"
                    onClick={createExample}
                    disabled={loading}
                    className="mb-2 flex w-full items-center gap-3 rounded-lg border-2 border-violet-600 bg-violet-50 px-3 py-2.5 text-left transition hover:bg-violet-100 disabled:opacity-60"
                  >
                    <Zap className="h-4 w-4 shrink-0 text-violet-700" />
                    <span className="min-w-0 flex-1">
                      <span className="block font-mono text-[12.5px] font-bold text-ink-900">
                        Crear repo de prueba Datgent
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-violet-700">
                        sandbox · recomendado
                      </span>
                    </span>
                  </button>
                  <div className="space-y-1.5">
                    {reposLoading && (
                      <div className="flex items-center gap-2 rounded-lg border-2 border-ink-200 bg-paper px-3 py-2.5 text-[12px] text-ink-500">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Cargando repositorios…
                      </div>
                    )}
                    {!reposLoading && repos.length === 0 && (
                      <p className="rounded-lg border-2 border-dashed border-ink-200 px-3 py-4 text-center text-[12px] text-ink-400">
                        No hay repos disponibles. Usa el repo de prueba.
                      </p>
                    )}
                    {!reposLoading && repos.map((r) => {
                      const sel = repo === r.full
                      return (
                        <button
                          key={r.full}
                          type="button"
                          onClick={() => setRepo(sel ? null : r.full)}
                          className={cn(
                            'flex w-full items-center gap-3 rounded-lg border-2 px-3 py-2.5 text-left transition-all',
                            sel
                              ? 'border-ink-900 bg-mint-50 shadow-hard-sm'
                              : 'border-ink-200 bg-paper hover:border-ink-900',
                          )}
                        >
                          <GitHubLogo className="h-4 w-4 shrink-0 text-ink-800" />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate font-mono text-[12.5px] font-medium text-ink-900">
                              {r.full}
                            </span>
                            <span className="font-mono text-[10px] uppercase tracking-wider text-ink-400">
                              {r.lang} · {r.priv ? 'privado' : 'público'}
                            </span>
                          </span>
                          <span
                            className={cn(
                              'grid h-5 w-5 shrink-0 place-items-center rounded border-2 transition',
                              sel
                                ? 'border-ink-900 bg-mint-500 text-ink-900'
                                : 'border-ink-200',
                            )}
                          >
                            {sel && <Check className="h-3 w-3" />}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className="flex gap-2.5 pt-1">
                  <Button
                    type="submit"
                    fullWidth
                    magnetic={false}
                    loading={loading}
                    disabled={name.trim().length < 2}
                  >
                    Crear tablero
                  </Button>
                  <Button type="button" variant="outline" magnetic={false} onClick={onClose}>
                    Cancelar
                  </Button>
                </div>
              </form>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
