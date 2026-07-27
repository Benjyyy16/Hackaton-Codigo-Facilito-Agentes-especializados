import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { LogIn, UserPlus, AlertCircle, Zap } from 'lucide-react'
import { useAppStore, DEMO_CREDENTIALS } from '@/store/AppStore'
import { login, register, storeToken, getMe } from '@/lib/authApi'

export default function Login() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { user, setUser, signInDemo } = useAppStore()

  // Si ya hay sesión, ir directo al dashboard
  useEffect(() => {
    if (user) navigate('/app', { replace: true })
  }, [user, navigate])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const tokens = mode === 'login'
        ? await login(email, password)
        : await register(email, name, password)
      storeToken(tokens.access_token)
      const me = await getMe(tokens.access_token)
      setUser({ id: me.id, name: me.name, email: me.email, avatar: '' })
      navigate('/app')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error inesperado')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-ink-950 px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-sm rounded-xl border-2 border-ink-800 bg-ink-900 p-6 shadow-lg"
      >
        <h1 className="mb-1 font-display text-2xl text-ink-100">
          {mode === 'login' ? 'Iniciar sesión' : 'Crear cuenta'}
        </h1>
        <p className="mb-6 text-sm text-ink-400">Datgent · Commitment Twin</p>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-900/30 px-3 py-2 text-sm text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1 block text-xs text-ink-400">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              placeholder="tu@email.com"
            />
          </div>

          {mode === 'register' && (
            <div>
              <label htmlFor="name" className="mb-1 block text-xs text-ink-400">Nombre</label>
              <input
                id="name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                placeholder="Tu nombre"
              />
            </div>
          )}

          <div>
            <label htmlFor="password" className="mb-1 block text-xs text-ink-400">Contraseña</label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-ink-100 placeholder:text-ink-500 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-500 disabled:opacity-50"
          >
            {loading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : mode === 'login' ? (
              <><LogIn className="h-4 w-4" /> Entrar</>
            ) : (
              <><UserPlus className="h-4 w-4" /> Crear cuenta</>
            )}
          </button>
        </form>

        <div className="mt-4 flex flex-col items-center gap-3">
          <p className="text-xs text-ink-400">
            {mode === 'login' ? (
              <>¿No tienes cuenta?{' '}
                <button onClick={() => { setMode('register'); setError('') }} className="text-violet-400 hover:underline">
                  Regístrate
                </button>
              </>
            ) : (
              <>¿Ya tienes cuenta?{' '}
                <button onClick={() => { setMode('login'); setError('') }} className="text-violet-400 hover:underline">
                  Inicia sesión
                </button>
              </>
            )}
          </p>

          <div className="w-full border-t border-ink-800 pt-3">
            <button
              type="button"
              onClick={() => { signInDemo(); navigate('/app') }}
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-violet-500/30 bg-violet-900/20 px-4 py-2 text-xs font-medium text-violet-300 transition-colors hover:bg-violet-900/40"
            >
              <Zap className="h-3.5 w-3.5" />
              Demo rápido ({DEMO_CREDENTIALS.email})
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
