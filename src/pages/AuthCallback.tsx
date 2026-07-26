import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { saveTokens } from '@/lib/api'
import { useAppStore } from '@/store/AppStore'
import { api } from '@/lib/api'

/**
 * Página que recibe los tokens JWT del OAuth callback del backend.
 * URL: /auth/callback?access_token=...&refresh_token=...&expires_in=...
 */
export default function AuthCallback() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { } = useAppStore()

  useEffect(() => {
    const accessToken = params.get('access_token')
    const refreshToken = params.get('refresh_token') || ''
    const expiresIn = parseInt(params.get('expires_in') || '3600', 10)

    if (!accessToken) {
      navigate('/', { replace: true })
      return
    }

    // Guardar tokens
    saveTokens({
      access_token: accessToken,
      refresh_token: refreshToken,
      token_type: 'bearer',
      expires_in: expiresIn,
    })

    // Obtener perfil y redirigir
    api.auth.me().then(() => {
      // Forzar reload para que AppStore levante la sesión desde tokens
      window.location.href = '/app'
    }).catch(() => {
      navigate('/', { replace: true })
    })
  }, [params, navigate])

  return (
    <div className="grid min-h-screen place-items-center" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-3">
        <span className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        <span className="text-[13px] text-ink-500">Conectando cuenta…</span>
      </div>
    </div>
  )
}
