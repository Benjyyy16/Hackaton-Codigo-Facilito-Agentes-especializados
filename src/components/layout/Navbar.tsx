import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence, motion, useMotionValueEvent, useScroll } from 'framer-motion'
import { Link, useNavigate } from 'react-router-dom'
import { LayoutGrid, Menu, PlayCircle, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { OrquestaMark } from '@/components/brand/Logos'
import { Avatar } from '@/components/ui/Avatar'
import { useAppStore } from '@/store/AppStore'
import { useFocusTrap } from '@/hooks/useFocusTrap'
import { cn } from '@/lib/cn'

const links = [
  { href: '#problema', label: 'Problema', n: '01' },
  { href: '#agentes', label: 'Agentes', n: '02' },
  { href: '#tablero', label: 'Tablero', n: '03' },
  { href: '#conexiones', label: 'Conexiones', n: '04' },
  { href: '#casos', label: 'Casos', n: '05' },
]

export function Navbar({
  onOpenAuth,
  onDemo,
}: {
  onOpenAuth: (mode: 'login' | 'signup') => void
  onDemo: () => void
}) {
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const { scrollY, scrollYProgress } = useScroll()
  const { user } = useAppStore()
  const navigate = useNavigate()

  useMotionValueEvent(scrollY, 'change', (v) => setScrolled(v > 20))

  const closeMobile = useCallback(() => setMobileOpen(false), [])
  /** El menú móvil ocupa toda la pantalla: se comporta como un diálogo. */
  const mobileRef = useFocusTrap<HTMLDivElement>(mobileOpen)

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [mobileOpen])

  useEffect(() => {
    if (!mobileOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMobile()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [mobileOpen, closeMobile])

  return (
    <>
      <motion.header
        initial={{ y: -80 }}
        animate={{ y: 0 }}
        transition={{ duration: 0.55, ease: [0.19, 1, 0.22, 1] }}
        className="fixed inset-x-0 top-0 z-50"
      >
        <div
          className={cn(
            'transition-all duration-300',
            scrolled
              ? 'border-b-2 border-ink-900 bg-paper/95 backdrop-blur-md'
              : 'border-b-2 border-transparent',
          )}
        >
          <div className="container-page flex h-[66px] items-center justify-between gap-4">
            {/* Marca */}
            <Link to="/" className="group flex items-center gap-2.5">
              <motion.span
                whileHover={{ rotate: -12, scale: 1.08 }}
                transition={{ type: 'spring', stiffness: 320, damping: 15 }}
                className="inline-block"
              >
                <OrquestaMark className="h-[34px] w-[34px]" />
              </motion.span>
              <span className="text-[16.5px] font-extrabold tracking-tight text-ink-900">
                Datgent
                <span className="text-violet-600">.</span>
              </span>
            </Link>

            {/* Links con índice */}
            <nav className="hidden items-center gap-0.5 lg:flex">
              {links.map((l) => (
                <a
                  key={l.href}
                  href={l.href}
                  className="group relative flex items-center gap-1.5 rounded-lg px-3 py-2 text-[13.5px] font-semibold text-ink-600 transition-colors hover:text-ink-900"
                >
                  <span className="font-mono text-[9.5px] text-ink-300 transition-colors group-hover:text-violet-600">
                    {l.n}
                  </span>
                  {l.label}
                  <span className="absolute bottom-1 left-3 h-[2px] w-0 bg-violet-600 transition-all duration-300 group-hover:w-[calc(100%-24px)]" />
                </a>
              ))}
            </nav>

            {/* Acciones */}
            <div className="flex items-center gap-2">
              {user ? (
                <>
                  <Button size="sm" variant="outline" onClick={() => navigate('/app')}>
                    <LayoutGrid className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Mis tableros</span>
                  </Button>
                  <Link
                    to="/perfil"
                    aria-label="Ver perfil"
                    className="rounded-full border-2 border-ink-900 transition-transform hover:-translate-y-0.5"
                  >
                    <Avatar name={user.name} hue={user.avatarHue} size={32} ring={false} />
                  </Link>
                </>
              ) : (
                <>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="hidden md:inline-flex"
                    onClick={onDemo}
                  >
                    <PlayCircle className="h-3.5 w-3.5 text-violet-600" />
                    Demo
                  </Button>
                  <Button size="sm" onClick={() => onOpenAuth('login')}>
                    Ingresar
                  </Button>
                </>
              )}

              <button
                onClick={() => setMobileOpen(true)}
                aria-label="Abrir menú de navegación"
                aria-expanded={mobileOpen}
                aria-controls="mobile-menu"
                className="grid h-9 w-9 place-items-center rounded-lg border-2 border-ink-900 bg-paper text-ink-900 transition hover:bg-violet-100 lg:hidden"
              >
                <Menu className="h-4 w-4" aria-hidden />
              </button>
            </div>
          </div>
        </div>

        {/* barra de progreso de lectura */}
        <motion.div
          style={{ scaleX: scrollYProgress }}
          className="h-[3px] origin-left bg-violet-600"
        />
      </motion.header>

      {/* Menú móvil */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            ref={mobileRef}
            id="mobile-menu"
            role="dialog"
            aria-modal="true"
            aria-label="Menú de navegación"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] overflow-y-auto bg-paper lg:hidden"
          >
            <div className="absolute inset-0 bg-grid bg-grid opacity-60" aria-hidden />

            <div className="container-page relative flex h-[66px] items-center justify-between border-b-2 border-ink-900">
              <span className="flex items-center gap-2.5">
                <OrquestaMark className="h-[34px] w-[34px]" />
                <span className="text-[16.5px] font-extrabold text-ink-900">Datgent</span>
              </span>
              <button
                onClick={closeMobile}
                aria-label="Cerrar menú"
                className="grid h-9 w-9 place-items-center rounded-lg border-2 border-ink-900 bg-paper text-ink-900"
              >
                <X className="h-4 w-4" aria-hidden />
              </button>
            </div>

            <nav className="container-page relative mt-8 flex flex-col gap-2 pb-10">
              {links.map((l, i) => (
                <motion.a
                  key={l.href}
                  href={l.href}
                  onClick={closeMobile}
                  initial={{ opacity: 0, x: -24 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  className="flex items-center gap-3 rounded-lg border-2 border-ink-900 bg-paper px-4 py-3.5 shadow-hard-sm"
                >
                  <span className="font-mono text-[11px] font-bold text-violet-600">{l.n}</span>
                  <span className="text-[15px] font-bold text-ink-900">{l.label}</span>
                </motion.a>
              ))}

              <div className="mt-6 flex flex-col gap-2.5">
                {user ? (
                  <Button
                    size="lg"
                    fullWidth
                    onClick={() => {
                      closeMobile()
                      navigate('/app')
                    }}
                  >
                    Mis tableros
                  </Button>
                ) : (
                  <>
                    <Button
                      size="lg"
                      fullWidth
                      onClick={() => {
                        closeMobile()
                        onOpenAuth('login')
                      }}
                    >
                      Ingresar
                    </Button>
                    <Button
                      size="lg"
                      variant="paper"
                      fullWidth
                      onClick={() => {
                        closeMobile()
                        onDemo()
                      }}
                    >
                      <PlayCircle className="h-4 w-4 text-violet-600" />
                      Entrar a la demo
                    </Button>
                  </>
                )}
              </div>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
