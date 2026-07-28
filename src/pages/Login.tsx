import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertTriangle, Eye, Github, Lock, Mail, PlayCircle, X, Zap } from 'lucide-react'
import { DEMO_CREDENTIALS, useAppStore } from '@/store/AppStore'
import { OrquestaMark } from '@/components/brand/Logos'
import { getStoredToken, oauthLoginUrl } from '@/lib/authApi'
import { getProvenance } from '@/lib/analysisApi'

export default function Login() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { user, signIn, signInDemo, signOut, sessionNotice } = useAppStore()

  /** `null` mientras se consulta; luego si el backend tiene GitHub conectado. */
  const [githubReady, setGithubReady] = useState<boolean | null>(null)
  const [redirecting, setRedirecting] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)

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

  function handleEmailLogin() {
    signIn(email || 'usuario@datgent.dev')
    navigate('/app', { replace: true })
  }

  function handleDemo() {
    signInDemo()
    navigate('/app', { replace: true })
  }

  function fillDemo() {
    setEmail(DEMO_CREDENTIALS.email)
    setPassword(DEMO_CREDENTIALS.password)
  }

  return (
    <div className="grid min-h-screen place-items-center bg-ink-950/55 px-4 py-10 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative w-full max-w-[620px] overflow-hidden rounded-2xl border-2 border-ink-900 bg-paper p-6 shadow-hard-lg sm:p-10"
      >
        <div className="absolute inset-x-0 top-0 h-3 bg-[repeating-linear-gradient(45deg,#ede7ff_0,#ede7ff_6px,transparent_6px,transparent_12px)]" />
        <button
          onClick={() => navigate('/')}
          aria-label="Cerrar"
          className="absolute right-5 top-5 grid h-11 w-11 place-items-center rounded-lg border-2 border-ink-900 bg-paper text-ink-900 shadow-hard-sm"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="mb-7 text-center">
          <OrquestaMark className="mx-auto h-16 w-16 rotate-3 shadow-hard-sm" />
          <h1 className="mt-5 font-display text-[34px] leading-none text-ink-900 sm:text-[40px]">
            {mode === 'signup' ? 'Creá tu cuenta' : 'Ingresá a Datgent'}
          </h1>
          <p className="mt-3 text-[16px] text-ink-500">Tus tableros y agentes te están esperando.</p>
          <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-ink-400">{title}</p>
        </div>

        {sessionNotice && (
          <div
            role="alert"
            className="mb-4 rounded-lg border-2 border-clay-500 bg-clay-100 px-3 py-2.5"
          >
            <p className="text-[12px] text-clay-700">{sessionNotice}</p>
          </div>
        )}

        {githubReady === false && (
          <div
            role="alert"
            className="mb-4 flex items-start gap-2.5 rounded-lg border-2 border-clay-500 bg-clay-100 px-3 py-2.5"
          >
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-clay-400" aria-hidden />
            <p className="text-[12px] leading-relaxed text-clay-700">
              GitHub OAuth no está disponible ahora. Podés ingresar con correo.
            </p>
          </div>
        )}

        <div className="mb-6 rounded-xl border-2 border-violet-500 bg-violet-50 p-4">
          <div className="flex items-start gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-lg border-2 border-ink-900 bg-violet-600 text-white shadow-hard-sm">
              <Zap className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[16px] font-extrabold text-ink-900">
                Cuenta demo · ver todas las vistas
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-500">
                3 proyectos, tableros canvas, kanban y perfil de equipo. Sin registro.
              </p>

              <div className="mt-3 rounded-lg border border-violet-200 bg-paper px-3 py-2 font-mono text-[11px] text-ink-700">
                <p className="flex justify-between gap-2">
                  <span className="uppercase tracking-wider text-ink-300">correo</span>
                  <span className="truncate font-bold">{DEMO_CREDENTIALS.email}</span>
                </p>
                <p className="mt-1 flex justify-between gap-2">
                  <span className="uppercase tracking-wider text-ink-300">clave</span>
                  <span className="font-bold">{DEMO_CREDENTIALS.password}</span>
                </p>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={handleDemo}
                  className="inline-flex items-center gap-2 rounded-lg border-2 border-ink-900 bg-violet-600 px-4 py-2 text-[14px] font-extrabold text-white shadow-hard-sm"
                >
                  <PlayCircle className="h-4 w-4" />
                  Entrar a la demo
                </button>
                <button
                  onClick={fillDemo}
                  className="rounded-lg border-2 border-ink-200 bg-paper px-4 py-2 text-[14px] font-extrabold text-ink-700"
                >
                  Autocompletar
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="mb-5 flex items-center gap-4">
          <span className="h-px flex-1 bg-ink-100" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-[0.24em] text-ink-300">
            con tu cuenta
          </span>
          <span className="h-px flex-1 bg-ink-100" />
        </div>

        <button
          onClick={handleGitHubLogin}
          disabled={redirecting}
          aria-label="Conectar con GitHub"
          aria-busy={redirecting}
          className="flex w-full items-center justify-center gap-3 rounded-xl border-2 border-ink-900 bg-ink-900 px-4 py-4 text-[16px] font-extrabold text-white shadow-hard-sm transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60"
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

        <div className="mt-6 space-y-4">
          <label className="block">
            <span className="label-mono text-ink-400">correo</span>
            <span className="mt-2 flex items-center gap-3 rounded-xl border-2 border-ink-900 bg-paper px-4 py-3">
              <Mail className="h-5 w-5 text-ink-300" />
              <input
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@empresa.com"
                className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-ink-300"
              />
            </span>
          </label>

          <label className="block">
            <span className="label-mono text-ink-400">contraseña</span>
            <span className="mt-2 flex items-center gap-3 rounded-xl border-2 border-ink-900 bg-paper px-4 py-3">
              <Lock className="h-5 w-5 text-ink-300" />
              <input
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                placeholder="••••••••"
                className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-ink-300"
              />
              <Eye className="h-5 w-5 text-ink-400" />
            </span>
          </label>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-[14px] font-semibold text-ink-600">
              <input
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                type="checkbox"
                className="h-5 w-5 accent-violet-600"
              />
              Mantener sesión
            </label>
            <button className="text-[14px] font-extrabold text-violet-700 underline">
              ¿Olvidaste tu contraseña?
            </button>
          </div>

          <button
            onClick={handleEmailLogin}
            className="w-full rounded-xl border-2 border-ink-900 bg-violet-600 px-4 py-4 text-[17px] font-extrabold text-white shadow-hard transition-transform hover:-translate-y-0.5"
          >
            Ingresá
          </button>
        </div>
      </motion.div>
    </div>
  )
}
