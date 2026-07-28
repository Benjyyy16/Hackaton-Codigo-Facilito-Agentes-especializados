import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertCircle, Check } from 'lucide-react'
import { useAppStore } from '@/store/AppStore'
import { clearToken, getMe, storeToken } from '@/lib/authApi'
import { errorMessage, isAbortError } from '@/lib/http'

/**
 * Recibe los tokens del callback OAuth del backend
 * (`GET /auth/oauth/{provider}/callback`, que redirige acá).
 *
 * Se aceptan tanto `?access_token=` como `#access_token=`: algunos flujos
 * devuelven los tokens en el fragmento para que no queden en los logs del
 * servidor. También se aceptan las dos rutas registradas en el router
 * (`/oauth/callback` y `/auth/callback`).
 */
export default function OAuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { setUser } = useAppStore()
  const [error, setError] = useState<string | null>(null)

  const readParam = useCallback(
    (name: string): string | null => {
      const fromQuery = searchParams.get(name)
      if (fromQuery) return fromQuery
      const hash = window.location.hash.replace(/^#/, '')
      if (!hash) return null
      return new URLSearchParams(hash).get(name)
    },
    [searchParams],
  )

  useEffect(() => {
    const controller = new AbortController()

    async function handleCallback() {
      const errorParam = readParam('error') ?? readParam('error_description')
      if (errorParam) {
        setError(errorParam)
        return
      }

      const token = readParam('access_token') ?? readParam('token')
      if (!token) {
        setError('No se recibió token de autenticación')
        return
      }

      const refreshToken = readParam('refresh_token') ?? undefined
      const expiresInRaw = readParam('expires_in')
      const expiresIn = expiresInRaw ? Number.parseInt(expiresInRaw, 10) : undefined

      storeToken(token, Number.isFinite(expiresIn) ? expiresIn : undefined, refreshToken)

      try {
        const me = await getMe(token, controller.signal)
        setUser({ id: me.id, name: me.name, email: me.email })
        navigate('/app', { replace: true })
      } catch (err) {
        if (isAbortError(err)) return
        // El token no sirvió: no dejarlo guardado para que no ensucie las
        // siguientes requests con un Bearer inválido
        clearToken()
        setError(errorMessage(err, 'Error al autenticar'))
      }
    }

    void handleCallback()
    return () => controller.abort()
  }, [readParam, setUser, navigate])

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center bg-ink-950 px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          role="alert"
          className="w-full max-w-sm rounded-xl border-2 border-rose-800 bg-rose-900/20 p-6"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" aria-hidden />
            <div className="min-w-0">
              <p className="text-sm font-bold text-rose-200">Error de autenticación</p>
              <p className="mt-1 break-words text-xs text-rose-300">{error}</p>
            </div>
          </div>
          <button
            onClick={() => navigate('/login', { replace: true })}
            className="mt-4 w-full rounded-lg bg-rose-600 px-4 py-2 text-sm text-white transition-colors hover:bg-rose-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
          >
            Volver a intentar
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
        role="status"
        aria-live="polite"
      >
        <div className="grid h-16 w-16 place-items-center rounded-full border-2 border-violet-500 bg-violet-900/20">
          <Check className="h-8 w-8 text-violet-400" aria-hidden />
        </div>
        <div className="text-center">
          <p className="text-sm font-bold text-ink-100">Autenticación exitosa</p>
          <p className="mt-1 text-xs text-ink-400">Redirigiendo…</p>
        </div>
        <span className="h-1 w-32 animate-pulse rounded-full bg-violet-500/30" />
      </motion.div>
    </div>
  )
}
