import { useEffect, useId, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Check,
  Eye,
  EyeOff,
  Lock,
  Mail,
  PlayCircle,
  ShieldCheck,
  User as UserIcon,
  X,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { GoogleLogo, GitHubLogo, OrquestaMark } from '@/components/brand/Logos'
import { DEMO_CREDENTIALS, useAppStore } from '@/store/AppStore'
import { api } from '@/lib/api'
import { cn } from '@/lib/cn'

type Mode = 'login' | 'signup'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

function scorePassword(pw: string) {
  let s = 0
  if (pw.length >= 8) s++
  if (pw.length >= 12) s++
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s++
  return Math.min(s, 4)
}

const strengthMeta = [
  { label: '—', bar: 'bg-ink-200', text: 'text-ink-400' },
  { label: 'Débil', bar: 'bg-rose-500', text: 'text-rose-600' },
  { label: 'Aceptable', bar: 'bg-clay-500', text: 'text-clay-700' },
  { label: 'Buena', bar: 'bg-violet-500', text: 'text-violet-700' },
  { label: 'Fuerte', bar: 'bg-mint-500', text: 'text-mint-700' },
]

export function AuthModal({
  open,
  onClose,
  initialMode = 'login',
  onSuccess,
}: {
  open: boolean
  onClose: () => void
  initialMode?: Mode
  onSuccess?: () => void
}) {
  const { signIn, signUp, signInDemo } = useAppStore()
  const [mode, setMode] = useState<Mode>(initialMode)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState<false | 'form' | 'demo' | 'oauth'>(false)
  const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string }>({})
  const [touched, setTouched] = useState(false)

  const ids = { name: useId(), email: useId(), password: useId(), title: useId() }

  useEffect(() => setMode(initialMode), [initialMode, open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  useEffect(() => {
    if (!open) {
      setPassword('')
      setShowPassword(false)
      setErrors({})
      setTouched(false)
      setLoading(false)
    }
  }, [open])

  const strength = useMemo(() => scorePassword(password), [password])

  function validate() {
    const next: typeof errors = {}
    if (mode === 'signup' && name.trim().length < 2) next.name = 'Escribí tu nombre completo.'
    if (!EMAIL_RE.test(email)) next.email = 'Ingresá un correo válido.'
    if (password.length < 8) next.password = 'Mínimo 8 caracteres.'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (!validate()) return
    setLoading('form')
    try {
      if (mode === 'login') await signIn(email, password)
      else await signUp({ name, email, password })
      onSuccess?.()
    } catch {
      /* error ya se muestra en authError */
    } finally {
      setLoading(false)
    }
  }

  /** Redirige al backend para login con OAuth */
  function handleOAuth(provider: 'google' | 'github') {
    setLoading('oauth')
    window.location.href = api.oauthLoginUrl(provider)
  }

  async function handleDemo() {
    setLoading('demo')
    await new Promise((r) => setTimeout(r, 550))
    signInDemo()
    setLoading(false)
    onSuccess?.()
  }

  function fillDemo() {
    setEmail(DEMO_CREDENTIALS.email)
    setPassword(DEMO_CREDENTIALS.password)
    setErrors({})
    setMode('login')
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
          <motion.button
            aria-label="Cerrar"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="absolute inset-0 cursor-default bg-ink-900/45 backdrop-blur-sm"
          />

          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby={ids.title}
            initial={{ opacity: 0, y: 30, scale: 0.96, rotate: -1.5 }}
            animate={{ opacity: 1, y: 0, scale: 1, rotate: 0 }}
            exit={{ opacity: 0, y: 18, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
            className="relative z-10 max-h-[92vh] w-full max-w-[430px] overflow-y-auto rounded-2xl border-2 border-ink-900 bg-paper shadow-hard-lg"
          >
            {/* franja rayada superior */}
            <div className="h-2 bg-hatch bg-[length:9px_9px]" />

            <button
              onClick={onClose}
              aria-label="Cerrar diálogo"
              className="absolute right-3.5 top-5 z-20 grid h-8 w-8 place-items-center rounded-lg border-2 border-ink-900 bg-paper text-ink-900 transition hover:bg-violet-100"
            >
              <X className="h-3.5 w-3.5" />
            </button>

            <div className="px-6 pb-7 pt-6 sm:px-8">
              {/* Cabecera */}
              <div className="flex flex-col items-center text-center">
                <motion.div
                  initial={{ rotate: -18, scale: 0.6, opacity: 0 }}
                  animate={{ rotate: 0, scale: 1, opacity: 1 }}
                  transition={{ type: 'spring', stiffness: 280, damping: 15, delay: 0.06 }}
                >
                  <OrquestaMark className="h-11 w-11" />
                </motion.div>

                <div className="mt-4 h-[62px]">
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.div
                      key={mode}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.22 }}
                    >
                      <h2
                        id={ids.title}
                        className="font-display text-[26px] leading-none tracking-tightest text-ink-900"
                      >
                        {mode === 'login' ? 'Ingresá a Datgent' : 'Creá tu cuenta'}
                      </h2>
                      <p className="mt-2 text-[13px] leading-relaxed text-ink-500">
                        {mode === 'login'
                          ? 'Tus tableros y agentes te están esperando.'
                          : 'Conectá tu primer repo en menos de un minuto.'}
                      </p>
                    </motion.div>
                  </AnimatePresence>
                </div>
              </div>

              {/* ====== Acceso demo destacado ====== */}
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.12 }}
                className="mt-1 rounded-xl border-2 border-violet-600 bg-violet-50 p-3.5"
              >
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border-2 border-ink-900 bg-violet-600">
                    <Zap className="h-4 w-4 text-white" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-bold text-ink-900">
                      Cuenta demo · ver todas las vistas
                    </p>
                    <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-600">
                      3 proyectos, tableros canvas, kanban y perfil de equipo. Sin registro.
                    </p>

                    <div className="mt-2.5 space-y-1 rounded-lg border border-violet-200 bg-paper px-2.5 py-2">
                      {[
                        { k: 'correo', v: DEMO_CREDENTIALS.email },
                        { k: 'clave', v: DEMO_CREDENTIALS.password },
                      ].map((c) => (
                        <div key={c.k} className="flex items-center justify-between gap-2">
                          <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
                            {c.k}
                          </span>
                          <span className="truncate font-mono text-[11px] font-medium text-ink-900">
                            {c.v}
                          </span>
                        </div>
                      ))}
                    </div>

                    <div className="mt-2.5 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="primary"
                        magnetic={false}
                        loading={loading === 'demo'}
                        onClick={handleDemo}
                      >
                        <PlayCircle className="h-3.5 w-3.5" />
                        Entrar a la demo
                      </Button>
                      <Button size="sm" variant="outline" magnetic={false} onClick={fillDemo}>
                        Autocompletar
                      </Button>
                    </div>
                  </div>
                </div>
              </motion.div>

              {/* Separador */}
              <div className="my-5 flex items-center gap-3">
                <span className="h-[2px] flex-1 bg-ink-100" />
                <span className="label-mono text-ink-400">o con tu cuenta</span>
                <span className="h-[2px] flex-1 bg-ink-100" />
              </div>

              {/* OAuth */}
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={() => handleOAuth('google')}
                  disabled={!!loading}
                  className="flex h-11 items-center justify-center gap-2 rounded-[10px] border-2 border-ink-900 bg-paper text-[13px] font-bold text-ink-900 shadow-hard-sm transition-all hover:-translate-y-0.5 active:translate-y-0 active:shadow-none disabled:opacity-55"
                >
                  <GoogleLogo className="h-[17px] w-[17px]" />
                  Google
                </button>
                <button
                  type="button"
                  onClick={() => handleOAuth('github')}
                  disabled={!!loading}
                  className="flex h-11 items-center justify-center gap-2 rounded-[10px] border-2 border-ink-900 bg-ink-900 text-[13px] font-bold text-white shadow-hard-sm transition-all hover:-translate-y-0.5 active:translate-y-0 active:shadow-none disabled:opacity-55"
                >
                  <GitHubLogo className="h-[17px] w-[17px]" />
                  GitHub
                </button>
              </div>

              {/* Formulario */}
              <form onSubmit={handleSubmit} noValidate className="mt-5 space-y-3.5">
                <AnimatePresence initial={false}>
                  {mode === 'signup' && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.26 }}
                      className="overflow-hidden"
                    >
                      <Field
                        id={ids.name}
                        label="Nombre"
                        icon={<UserIcon className="h-4 w-4" />}
                        error={touched ? errors.name : undefined}
                      >
                        <input
                          id={ids.name}
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          autoComplete="name"
                          placeholder="Ada Lovelace"
                          className="h-11 w-full bg-transparent pl-10 pr-3 text-[14px] text-ink-900 placeholder:text-ink-300 focus:outline-none"
                        />
                      </Field>
                    </motion.div>
                  )}
                </AnimatePresence>

                <Field
                  id={ids.email}
                  label="Correo"
                  icon={<Mail className="h-4 w-4" />}
                  error={touched ? errors.email : undefined}
                >
                  <input
                    id={ids.email}
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="email"
                    placeholder="tu@empresa.com"
                    aria-invalid={touched && !!errors.email}
                    className="h-11 w-full bg-transparent pl-10 pr-3 text-[14px] text-ink-900 placeholder:text-ink-300 focus:outline-none"
                  />
                </Field>

                <Field
                  id={ids.password}
                  label="Contraseña"
                  icon={<Lock className="h-4 w-4" />}
                  error={touched ? errors.password : undefined}
                  trailing={
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                      aria-pressed={showPassword}
                      title={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                      className="grid h-8 w-8 place-items-center rounded-md border-2 border-transparent text-ink-400 transition hover:border-ink-900 hover:bg-violet-100 hover:text-ink-900"
                    >
                      <AnimatePresence mode="wait" initial={false}>
                        <motion.span
                          key={showPassword ? 'off' : 'on'}
                          initial={{ opacity: 0, scale: 0.6, rotate: -30 }}
                          animate={{ opacity: 1, scale: 1, rotate: 0 }}
                          exit={{ opacity: 0, scale: 0.6, rotate: 30 }}
                          transition={{ duration: 0.15 }}
                          className="grid place-items-center"
                        >
                          {showPassword ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </motion.span>
                      </AnimatePresence>
                    </button>
                  }
                >
                  <input
                    id={ids.password}
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    placeholder="••••••••"
                    aria-invalid={touched && !!errors.password}
                    aria-describedby={mode === 'signup' ? `${ids.password}-strength` : undefined}
                    className="h-11 w-full bg-transparent pl-10 pr-1 text-[14px] text-ink-900 placeholder:text-ink-300 focus:outline-none"
                  />
                </Field>

                {/* Fuerza: bloques cuadrados */}
                <AnimatePresence initial={false}>
                  {mode === 'signup' && password.length > 0 && (
                    <motion.div
                      id={`${ids.password}-strength`}
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="flex items-center gap-2.5 pt-0.5">
                        <div className="flex flex-1 gap-1">
                          {[1, 2, 3, 4].map((i) => (
                            <span
                              key={i}
                              className="h-2 flex-1 overflow-hidden rounded-sm border border-ink-200"
                            >
                              <motion.span
                                className={cn('block h-full', strengthMeta[strength].bar)}
                                initial={{ width: 0 }}
                                animate={{ width: strength >= i ? '100%' : 0 }}
                                transition={{ duration: 0.28, delay: i * 0.04 }}
                              />
                            </span>
                          ))}
                        </div>
                        <span
                          className={cn(
                            'w-[74px] text-right font-mono text-[10px] font-bold uppercase tracking-wider',
                            strengthMeta[strength].text,
                          )}
                        >
                          {strengthMeta[strength].label}
                        </span>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {mode === 'login' && (
                  <div className="flex items-center justify-between pt-0.5">
                    <label className="group flex cursor-pointer select-none items-center gap-2 text-[12.5px] font-medium text-ink-600">
                      <span className="relative grid h-[18px] w-[18px] place-items-center">
                        <input type="checkbox" defaultChecked className="peer sr-only" />
                        <span className="h-[18px] w-[18px] rounded border-2 border-ink-900 bg-paper transition peer-checked:bg-violet-600" />
                        <Check className="pointer-events-none absolute h-3 w-3 text-white opacity-0 transition peer-checked:opacity-100" />
                      </span>
                      Mantener sesión
                    </label>
                    <button
                      type="button"
                      className="text-[12.5px] font-bold text-violet-700 underline decoration-violet-300 decoration-2 underline-offset-[3px] transition hover:decoration-violet-600"
                    >
                      ¿Olvidaste tu contraseña?
                    </button>
                  </div>
                )}

                <Button
                  type="submit"
                  size="lg"
                  fullWidth
                  magnetic={false}
                  loading={loading === 'form'}
                  className="mt-1"
                >
                  {mode === 'login' ? 'Ingresá' : 'Crear cuenta'}
                </Button>
              </form>

              {/* Alternar */}
              <div className="mt-5 border-t-2 border-dashed border-ink-200 pt-4 text-center">
                <p className="text-[13px] text-ink-600">
                  {mode === 'login' ? '¿Todavía no tenés cuenta?' : '¿Ya tenés una cuenta?'}{' '}
                  <button
                    type="button"
                    onClick={() => {
                      setMode((m) => (m === 'login' ? 'signup' : 'login'))
                      setTouched(false)
                      setErrors({})
                    }}
                    className="font-bold text-violet-700 underline decoration-violet-300 decoration-2 underline-offset-[3px] transition hover:decoration-violet-600"
                  >
                    {mode === 'login' ? 'Crear cuenta' : 'Ingresá'}
                  </button>
                </p>
              </div>

              <p className="mt-4 flex items-center justify-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-400">
                <ShieldCheck className="h-3 w-3 text-mint-600" />
                cifrado en tránsito · oauth con scopes mínimos
              </p>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

/* ---------------- Campo ---------------- */

function Field({
  id,
  label,
  icon,
  error,
  trailing,
  children,
}: {
  id: string
  label: string
  icon: React.ReactNode
  error?: string
  trailing?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div>
      <label htmlFor={id} className="label-mono mb-1.5 block text-ink-500">
        {label}
      </label>
      <div
        className={cn(
          'group relative flex items-center rounded-[10px] border-2 bg-paper transition-colors',
          error ? 'border-rose-500' : 'border-ink-900 focus-within:border-violet-600',
        )}
      >
        <span
          aria-hidden
          className={cn(
            'pointer-events-none absolute left-3 transition-colors',
            error ? 'text-rose-500' : 'text-ink-300 group-focus-within:text-violet-600',
          )}
        >
          {icon}
        </span>
        {children}
        {trailing && <span className="pr-1.5">{trailing}</span>}
      </div>
      <AnimatePresence>
        {error && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden pt-1 text-[12px] font-medium text-rose-600"
          >
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}
