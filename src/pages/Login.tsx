import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Github } from 'lucide-react'
import { useAppStore } from '@/store/AppStore'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export default function Login() {
  const navigate = useNavigate()
  const { user } = useAppStore()

  // Si ya hay sesión, ir directo al dashboard
  useEffect(() => {
    if (user) navigate('/app', { replace: true })
  }, [user, navigate])

  function handleGitHubLogin() {
    // Redirect a OAuth flow del backend
    window.location.href = `${BACKEND_URL}/oauth/github/authorize`
  }

  return (
    <div className="grid min-h-screen place-items-center bg-ink-950 px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-sm rounded-xl border-2 border-ink-800 bg-ink-900 p-8 shadow-lg"
      >
        {/* Logo/Title */}
        <div className="mb-8 text-center">
          <h1 className="font-display text-3xl text-ink-100">Datgent</h1>
          <p className="mt-2 text-sm text-ink-400">Commitment Twin · Risk Analysis</p>
        </div>

        {/* GitHub OAuth Button */}
        <button
          onClick={handleGitHubLogin}
          className="flex w-full items-center justify-center gap-3 rounded-lg border-2 border-ink-700 bg-ink-800 px-4 py-3.5 text-sm font-medium text-ink-100 transition-all hover:border-violet-500 hover:bg-ink-700"
        >
          <Github className="h-5 w-5" />
          Conectar con GitHub
        </button>

        {/* Info */}
        <div className="mt-6 space-y-2 rounded-lg bg-ink-950/50 px-4 py-3">
          <p className="text-xs leading-relaxed text-ink-400">
            Datgent analiza riesgos en tus repositorios de GitHub. Para comenzar, conecta tu cuenta.
          </p>
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-500">
            ✓ Solo lectura · ✓ Sin compartir datos
          </p>
        </div>
      </motion.div>
    </div>
  )
}
