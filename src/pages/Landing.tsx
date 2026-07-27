import { useNavigate } from 'react-router-dom'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { Hero } from '@/components/landing/Hero'
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

  function openAuth(_mode: 'login' | 'signup') {
    navigate('/login')
  }

  /** Atajo: entra con la cuenta demo directo al dashboard. */
  function enterDemo() {
    signInDemo()
    navigate('/app')
  }

  return (
    <>
      <Navbar onOpenAuth={openAuth} onDemo={enterDemo} />

      <main>
        <Hero onOpenAuth={openAuth} onDemo={enterDemo} />
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
