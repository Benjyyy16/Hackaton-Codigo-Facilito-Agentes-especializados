import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { GitBranch, Search, AlertCircle, Play, Zap } from 'lucide-react'
import { connectGitHubUrl, listUserRepos, type GitHubRepo } from '@/lib/githubApi'
import { startAnalysisFromRepo } from '@/lib/analysisApi'
import { GitHubLogo } from '@/components/brand/Logos'
import { Button } from '@/components/ui/Button'
import { LoadingRegion, RepoRowSkeleton } from '@/components/ui/Skeleton'
import { errorMessage, isAbortError, isHttpError } from '@/lib/http'

export default function RepoSelector() {
  const [repos, setRepos] = useState<GitHubRepo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  /** `true` cuando el backend no expone repos (GitHub sin conectar). */
  const [reposUnavailable, setReposUnavailable] = useState(false)
  const [search, setSearch] = useState('')
  const [starting, setStarting] = useState<string | null>(null)
  const [connecting, setConnecting] = useState(false)
  const navigate = useNavigate()

  /** `null` si la sesión ya no sirve: sin JWT no se puede iniciar la vinculación. */
  const connectUrl = useMemo(() => connectGitHubUrl(), [])

  /**
   * Sale del SPA a propósito: el backend responde con redirecciones hacia
   * GitHub, así que tiene que navegar el browser y no un fetch.
   */
  const connect = useCallback(() => {
    if (!connectUrl) return
    setConnecting(true)
    window.location.assign(connectUrl)
  }, [connectUrl])

  /** Cancela el arranque anterior si el usuario elige otro repo. */
  const startAbortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    listUserRepos(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return
        setRepos(data)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted || isAbortError(err)) return
        // 404/503 = la instancia no tiene el proxy de GitHub disponible:
        // no es un error del usuario, así que se ofrece el caso demo
        if (isHttpError(err) && [404, 501, 503].includes(err.status)) {
          setReposUnavailable(true)
        } else {
          setError(errorMessage(err, 'Error cargando repositorios'))
        }
        setLoading(false)
      })

    return () => controller.abort()
  }, [])

  useEffect(() => () => startAbortRef.current?.abort(), [])

  const launch = useCallback(
    async (repo: GitHubRepo | null) => {
      startAbortRef.current?.abort()
      const controller = new AbortController()
      startAbortRef.current = controller

      setStarting(repo?.full_name ?? '__demo__')
      setError(null)
      try {
        const target = repo ?? {
          full_name: 'datgent/demo',
          description: 'Caso de demostración del análisis multiagente',
          default_branch: 'main',
          language: null,
        }
        const { session_id } = await startAnalysisFromRepo(target, { signal: controller.signal })
        navigate(`/app/datgent?session=${session_id}`, { replace: true })
      } catch (err: unknown) {
        if (isAbortError(err)) return
        setError(errorMessage(err, 'Error iniciando análisis'))
        setStarting(null)
      }
    },
    [navigate],
  )

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return repos
    return repos.filter(
      (r) =>
        r.full_name.toLowerCase().includes(q) ||
        (r.description ? r.description.toLowerCase().includes(q) : false),
    )
  }, [repos, search])

  return (
    <div className="min-h-screen bg-ink-50 px-4 py-8 sm:py-12">
      <div className="mx-auto w-full max-w-4xl">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-display text-[26px] leading-tight text-ink-900 sm:text-3xl">
            Selecciona un repositorio
          </h1>
          <p className="mt-2 text-[13px] text-ink-600 sm:text-sm">
            Datgent analizará riesgos y compromisos en el repositorio seleccionado
          </p>
        </motion.div>

        {/* Error accionable, sin sacar al usuario de la pantalla */}
        {error && (
          <div
            role="alert"
            className="mt-5 flex flex-col gap-3 rounded-xl border-2 border-rose-200 bg-rose-50 p-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex min-w-0 items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" aria-hidden />
              <p className="min-w-0 break-words text-[12.5px] text-rose-800">{error}</p>
            </div>
            <button
              onClick={() => navigate('/app')}
              className="shrink-0 rounded-lg border-2 border-rose-300 bg-white px-3 py-1.5 text-[12.5px] font-semibold text-rose-700 transition hover:border-rose-600"
            >
              Volver al dashboard
            </button>
          </div>
        )}

        {/* GitHub sin vincular → ofrecer conectar, con el demo como salida */}
        {reposUnavailable && !loading && (
          <div className="mt-5 rounded-xl border-2 border-clay-300 bg-clay-100 p-4">
            <p className="text-[13px] font-bold text-clay-700">
              Conectá tu cuenta de GitHub
            </p>
            <p className="mt-1 text-[12.5px] leading-relaxed text-clay-700">
              Para listar tus repositorios necesitamos permiso de lectura sobre ellos. Iniciar
              sesión con GitHub no lo incluye, así que es un paso aparte que se hace una sola vez.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {connectUrl && (
                <Button size="sm" onClick={() => void connect()} loading={connecting}>
                  <GitHubLogo className="h-3.5 w-3.5" />
                  Conectar GitHub
                </Button>
              )}
              <button
                onClick={() => void launch(null)}
                disabled={starting !== null || connecting}
                className="inline-flex items-center gap-1.5 rounded-lg border-2 border-clay-400 bg-white px-3 py-1.5 text-[12.5px] font-semibold text-clay-700 transition hover:border-clay-600 disabled:opacity-60"
              >
                <Zap className="h-3.5 w-3.5" aria-hidden />
                {starting === '__demo__' ? 'Iniciando…' : 'Usar caso demo'}
              </button>
            </div>
            {!connectUrl && (
              <p className="mt-2 text-[11.5px] text-clay-700">
                Tu sesión expiró. Volvé a iniciar sesión para conectar GitHub.
              </p>
            )}
          </div>
        )}

        {/* Buscador */}
        {!reposUnavailable && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mt-6"
          >
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
                aria-hidden
              />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar repositorio…"
                aria-label="Buscar repositorio"
                disabled={loading}
                className="w-full rounded-xl border-2 border-ink-200 bg-white py-3 pl-11 pr-4 text-sm text-ink-900 placeholder:text-ink-400 focus:border-violet-500 focus:outline-none disabled:opacity-60"
              />
            </div>
          </motion.div>
        )}

        {/* Lista */}
        <div className="mt-6 space-y-3">
          {loading ? (
            <LoadingRegion label="Cargando repositorios">
              <div className="space-y-3">
                {Array.from({ length: 4 }, (_, i) => (
                  <RepoRowSkeleton key={i} />
                ))}
              </div>
            </LoadingRegion>
          ) : reposUnavailable ? null : filtered.length === 0 ? (
            <p className="rounded-xl border-2 border-dashed border-ink-200 py-12 text-center text-sm text-ink-400">
              {search ? 'No se encontraron repositorios' : 'No tienes repositorios'}
            </p>
          ) : (
            <ul className="space-y-3">
              {filtered.map((repo, i) => (
                <motion.li
                  key={repo.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  // El escalonado se corta pronto: con 50 repos la última fila
                  // tardaría segundos en aparecer
                  transition={{ delay: 0.15 + Math.min(i, 8) * 0.05 }}
                  className="group relative overflow-hidden rounded-xl border-2 border-ink-200 bg-white shadow-sm transition-all hover:border-violet-500 hover:shadow-md"
                >
                  <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                    <div className="flex min-w-0 flex-1 items-start gap-3">
                      <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border-2 border-ink-900 bg-paper">
                        <GitBranch className="h-4 w-4 text-ink-700" aria-hidden />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold text-ink-900">{repo.full_name}</p>
                        {repo.description && (
                          <p className="mt-0.5 line-clamp-2 text-xs text-ink-600">
                            {repo.description}
                          </p>
                        )}
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px]">
                          {repo.language && (
                            <span className="rounded border border-ink-300 bg-ink-50 px-1.5 py-0.5 font-mono text-ink-700">
                              {repo.language}
                            </span>
                          )}
                          {repo.private && (
                            <span className="rounded border border-clay-400 bg-clay-100 px-1.5 py-0.5 font-mono text-clay-700">
                              PRIVATE
                            </span>
                          )}
                          <span className="font-mono text-ink-400">
                            ⭐ {repo.stargazers_count}
                          </span>
                        </div>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      className="w-full sm:w-auto"
                      onClick={() => void launch(repo)}
                      loading={starting === repo.full_name}
                      disabled={starting !== null}
                      aria-label={`Analizar ${repo.full_name}`}
                    >
                      <Play className="h-3.5 w-3.5" aria-hidden />
                      Analizar
                    </Button>
                  </div>
                </motion.li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
