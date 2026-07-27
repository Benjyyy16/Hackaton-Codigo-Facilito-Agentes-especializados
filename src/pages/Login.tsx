import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, Github, Zap } from 'lucide-react'
import { useAppStore } from '@/store/AppStore'
import { getStoredToken, oauthLoginUrl } from '@/lib/authApi'
import { getProvenance } from '@/lib/analysisApi'

export default function Login() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { user, signInDemo, signOut, sessionNotice } = useAppStore()

  /** `null` mientras se consulta; luego si el backend tiene GitHub conectado. */
  const [githubReady, setGithubReady] = useState<boolean | null>(null)
  const [redirecting, setRedirecting] = useState(false)

  const mode = params.get('mode') === 'signup' ? 'signup' : 'login'

  /**
   * Sesión guardada sin token: quedó a medias (token vencido y borrado, o
   * localStorage editado a mano). Se limpia en vez de dejar entrar a la app
   * con un usuario que el backend va a rechazar.
   *
   * La cuenta demo se exceptúa: nunca tiene token porque no pasa por el backend.
   */
  useEffect(() => {
    if (!user) return
    if (!user.isDemo && !getStoredToken()) {
      signOut()
      return
    }
    navigate('/app', { replace: true })
  }, [user, navigate, signOut])

  /**
   * `GET /live/provenance` dice qué providers están realmente conectados.
   * Sirve para no mandar al usuario a un OAuth que responderá
   * "503 · Falta GITHUB_CLIENT_ID" y dejarlo en una pantalla de error.
   */
  useEffect(() => {
    const controller = new AbortController()
    getProvenance({ signal: controller.signal, timeoutMs: 12_000 })
      .then(({ providers }) => {
        const github = providers.find((p) => p.provider === 'github')
        setGithubReady(Boolean(github?.connected))
      })
      .catch(() => setGithubReady(false))
    return () => controller.abort()
  }, [])

  const title = useMemo(
    () => (mode === 'signup' ? 'Creá tu cuenta' : 'Iniciá sesión'),
    [mode],
  )

  function handleGitHubLogin() {
    setRedirecting(true)
    // Flujo real del backend: GET /auth/oauth/github/login → provider → callback
    window.location.href = oauthLoginUrl('github')
  }

  function handleDemo() {
    signInDemo()
    navigate('/app', { replace: true })
  }

  return (
    <div className="grid min-h-screen place-items-center bg-ink-950 px-4 py-10">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-sm rounded-xl border-2 border-ink-800 bg-ink-900 p-6 shadow-lg sm:p-8"
      >
        <div className="mb-7 text-center">
          <h1 className="font-display text-[28px] leading-none text-ink-100 sm:text-3xl">Datgent</h1>
          <p className="mt-2 text-[13px] text-ink-400">Commitment Twin · Risk Analysis</p>
          <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-ink-500">{title}</p>
        </div>

        {sessionNotice && (
          <div
            role="alert"
            className="mb-4 rounded-lg border-2 border-clay-500 bg-clay-500/10 px-3 py-2.5"
          >
            <p className="text-[12px] text-clay-300">{sessionNotice}</p>
          </div>
        )}

        {githubReady === false && (
          <div
            role="alert"
            className="mb-4 flex items-start gap-2.5 rounded-lg border-2 border-clay-500 bg-clay-500/10 px-3 py-2.5"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-clay-400" aria-hidden />
            <p className="text-[12px] leading-relaxed text-clay-200">
              El backend no tiene GitHub OAuth configurado. Podés recorrer todo el análisis con la
              cuenta demo.
            </p>
          </div>
        )}

        <button
          onClick={handleGitHubLogin}
          disabled={redirecting}
          aria-label="Conectar con GitHub"
          aria-busy={redirecting}
          className="flex w-full items-center justify-center gap-3 rounded-lg border-2 border-ink-700 bg-ink-800 px-4 py-3.5 text-sm font-medium text-ink-100 transition-all hover:border-violet-500 hover:bg-ink-700 focus-visible:border-violet-400 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
        >
          {redirecting ? (
            <span
              aria-hidden
              className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
            />
          ) : (
            <Github className="h-5 w-5" aria-hidden />
          )}
          {redirecting ? 'Redirigiendo…' : 'Conectar con GitHub'}
        </button>

        <div className="my-4 flex items-center gap-3">
          <span className="h-px flex-1 bg-ink-800" />
          <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-500">o</span>
          <span className="h-px flex-1 bg-ink-800" />
        </div>

        <button
          onClick={handleDemo}
          aria-label="Entrar con la cuenta de demostración"
          className="flex w-full items-center justify-center gap-2.5 rounded-lg border-2 border-violet-600 bg-violet-600/15 px-4 py-3 text-sm font-medium text-violet-200 transition-all hover:bg-violet-600/30 focus-visible:border-violet-400 focus-visible:outline-none"
        >
          <Zap className="h-4 w-4" aria-hidden />
          Entrar con la cuenta demo
        </button>

        <div className="mt-6 space-y-2 rounded-lg bg-ink-950/50 px-4 py-3">
          <p className="text-[11.5px] leading-relaxed text-ink-400">
            Datgent analiza riesgos en tus repositorios de GitHub. Para comenzar, conectá tu cuenta.
          </p>
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-500">
            ✓ Solo lectura · ✓ Sin compartir datos
          </p>
        </div>
      </motion.div>
    </div>
  )
}
