import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Hero } from '@/components/landing/Hero'
import { LiveProductShowcase } from '@/components/landing/LiveProductShowcase'
import { ProblemStats } from '@/components/landing/ProblemStats'
import { AgentsSection } from '@/components/landing/AgentsSection'
import { CanvasShowcase } from '@/components/landing/CanvasShowcase'
import { Integrations } from '@/components/landing/Integrations'
import { UseCases } from '@/components/landing/UseCases'
import { HowItWorks } from '@/components/landing/HowItWorks'
import { Faq } from '@/components/landing/Faq'
import { FinalCta } from '@/components/landing/FinalCta'
import { useAppStore } from '@/store/AppStore'

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
        <LiveProductShowcase />
        <ProblemStats />
        <AgentsSection />
        {/* El tablero canvas va antes de las conexiones */}
        <CanvasShowcase />
        <Integrations />
        <UseCases />
        <HowItWorks />
        <Faq />
        <FinalCta onOpenAuth={openAuth} onDemo={enterDemo} />
      </main>

      <Footer />
    </>
  )
}
