import { lazy, Suspense, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Hero } from '@/components/landing/Hero'
import { useAppStore } from '@/store/AppStore'

const ProblemStats = lazy(() =>
  import('@/components/landing/ProblemStats').then((m) => ({ default: m.ProblemStats })),
)
const AgentsSection = lazy(() =>
  import('@/components/landing/AgentsSection').then((m) => ({ default: m.AgentsSection })),
)
const CanvasShowcase = lazy(() =>
  import('@/components/landing/CanvasShowcase').then((m) => ({ default: m.CanvasShowcase })),
)
const Integrations = lazy(() =>
  import('@/components/landing/Integrations').then((m) => ({ default: m.Integrations })),
)
const UseCases = lazy(() =>
  import('@/components/landing/UseCases').then((m) => ({ default: m.UseCases })),
)
const HowItWorks = lazy(() =>
  import('@/components/landing/HowItWorks').then((m) => ({ default: m.HowItWorks })),
)
const Faq = lazy(() => import('@/components/landing/Faq').then((m) => ({ default: m.Faq })))
const FinalCta = lazy(() =>
  import('@/components/landing/FinalCta').then((m) => ({ default: m.FinalCta })),
)

function LandingSectionsFallback() {
  return <div className="container-page h-24" aria-hidden />
}

export default function Landing() {
  const { signInDemo } = useAppStore()
  const navigate = useNavigate()

  /**
   * La autenticación vive en `/login` (OAuth del backend), no en un modal:
   * el flujo sale del navegador hacia el provider y vuelve por callback, así
   * que una página propia es lo que corresponde.
   */
  const openAuth = useCallback(
    (mode: 'login' | 'signup') => {
      navigate(`/login?mode=${mode}`)
    },
    [navigate],
  )

  /** Atajo: entra con la cuenta demo directo al dashboard. */
  const enterDemo = useCallback(() => {
    signInDemo()
    navigate('/app')
  }, [signInDemo, navigate])

  return (
    <>
      <Navbar onOpenAuth={openAuth} onDemo={enterDemo} />

      <main>
        <Hero onOpenAuth={openAuth} onDemo={enterDemo} />
        <Suspense fallback={<LandingSectionsFallback />}>
          <ProblemStats />
          <AgentsSection />
          <CanvasShowcase />
          <Integrations />
          <UseCases />
          <HowItWorks />
          <Faq />
          <FinalCta onOpenAuth={openAuth} onDemo={enterDemo} />
        </Suspense>
      </main>

      <Footer />
    </>
  )
}
