import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { GitBranch, Search, Loader2, AlertCircle, Play } from 'lucide-react'
import { listUserRepos, type GitHubRepo } from '@/lib/githubApi'
import { startAnalysisFromRepo } from '@/lib/analysisApi'
import { Button } from '@/components/ui/Button'

export default function RepoSelector() {
  const [repos, setRepos] = useState<GitHubRepo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [starting, setStarting] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      try {
        const data = await listUserRepos()
        setRepos(data)
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Error cargando repositorios')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  async function handleSelectRepo(repo: GitHubRepo) {
    setStarting(repo.full_name)
    try {
      const { session_id } = await startAnalysisFromRepo(repo)
      navigate(`/app/datgent?session=${session_id}`, { replace: true })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error iniciando análisis')
      setStarting(null)
    }
  }

  const filtered = repos.filter(r =>
    r.full_name.toLowerCase().includes(search.toLowerCase()) ||
    (r.description && r.description.toLowerCase().includes(search.toLowerCase()))
  )

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-violet-600" />
          <p className="text-sm text-ink-600">Cargando repositorios...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-50 px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md rounded-xl border-2 border-red-200 bg-red-50 p-6"
        >
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-600" />
            <div>
              <p className="text-sm font-bold text-red-900">Error</p>
              <p className="mt-1 text-xs text-red-700">{error}</p>
            </div>
          </div>
          <button
            onClick={() => navigate('/app')}
            className="mt-4 w-full rounded-lg bg-red-600 px-4 py-2 text-sm text-white transition-colors hover:bg-red-500"
          >
            Volver al dashboard
          </button>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-ink-50 px-4 py-12">
      <div className="mx-auto w-full max-w-4xl">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-display text-3xl text-ink-900">Selecciona un repositorio</h1>
          <p className="mt-2 text-sm text-ink-600">
            Datgent analizará riesgos y compromisos en el repositorio seleccionado
          </p>
        </motion.div>

        {/* Buscador */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mt-6"
        >
          <div className="relative">
            <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar repositorio..."
              className="w-full rounded-xl border-2 border-ink-200 bg-white py-3 pl-11 pr-4 text-sm text-ink-900 placeholder:text-ink-400 focus:border-violet-500 focus:outline-none"
            />
          </div>
        </motion.div>

        {/* Lista de repos */}
        <div className="mt-6 space-y-3">
          {filtered.length === 0 ? (
            <p className="rounded-xl border-2 border-dashed border-ink-200 py-12 text-center text-sm text-ink-400">
              {search ? 'No se encontraron repositorios' : 'No tienes repositorios'}
            </p>
          ) : (
            filtered.map((repo, i) => (
              <motion.div
                key={repo.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 + i * 0.05 }}
                className="group relative overflow-hidden rounded-xl border-2 border-ink-200 bg-white shadow-sm transition-all hover:border-violet-500 hover:shadow-md"
              >
                <div className="flex items-center justify-between gap-4 p-4">
                  <div className="flex min-w-0 flex-1 items-start gap-3">
                    <div className="mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-lg border-2 border-ink-900 bg-paper">
                      <GitBranch className="h-4 w-4 text-ink-700" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold text-ink-900">{repo.full_name}</p>
                      {repo.description && (
                        <p className="mt-0.5 line-clamp-1 text-xs text-ink-600">{repo.description}</p>
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
                        <span className="font-mono text-ink-400">⭐ {repo.stargazers_count}</span>
                      </div>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => handleSelectRepo(repo)}
                    loading={starting === repo.full_name}
                    disabled={starting !== null}
                  >
                    <Play className="h-3.5 w-3.5" />
                    Analizar
                  </Button>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
