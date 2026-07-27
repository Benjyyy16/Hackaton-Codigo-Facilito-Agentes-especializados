import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertCircle, Check } from 'lucide-react'
import { useAppStore } from '@/store/AppStore'
import { getMe, storeToken } from '@/lib/authApi'

export default function OAuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setUser } = useAppStore()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function handleCallback() {
      const token = searchParams.get('access_token')
      const errorParam = searchParams.get('error')

      if (errorParam) {
        setError(errorParam)
        return
      }

      if (!token) {
        setError('No se recibió token de autenticación')
        return
      }

      try {
        // Guardar token
        storeToken(token)

        // Obtener user info
        const me = await getMe(token)
        setUser({ id: me.id, name: me.name, email: me.email, avatar: '' })

        // Navegar a selector de repo
        navigate('/app/datgent/select-repo', { replace: true })
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Error al autenticar')
      }
    }

    handleCallback()
  }, [searchParams, setUser, navigate])

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-950 px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-sm rounded-xl border-2 border-red-800 bg-red-900/20 p-6"
        >
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 shrink-0 text-red-400" />
            <div>
              <p className="text-sm font-bold text-red-200">Error de autenticación</p>
              <p className="mt-1 text-xs text-red-300">{error}</p>
            </div>
          </div>
          <button
            onClick={() => navigate('/login')}
            className="mt-4 w-full rounded-lg bg-red-600 px-4 py-2 text-sm text-white transition-colors hover:bg-red-500"
          >
            Reintentar
          </button>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="grid min-h-screen place-items-center bg-ink-950 px-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex flex-col items-center gap-4"
      >
        <div className="grid h-16 w-16 place-items-center rounded-full border-2 border-violet-500 bg-violet-900/20">
          <Check className="h-8 w-8 text-violet-400" />
        </div>
        <div className="text-center">
          <p className="text-sm font-bold text-ink-100">Autenticación exitosa</p>
          <p className="mt-1 text-xs text-ink-400">Redirigiendo...</p>
        </div>
        <span className="h-1 w-32 animate-pulse rounded-full bg-violet-500/30" />
      </motion.div>
    </div>
  )
}
