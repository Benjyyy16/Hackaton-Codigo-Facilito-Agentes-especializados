import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'

/**
 * Fondo minimalista con dots sutiles y gradientes suaves.
 * Inspirado en aguilarb.tech: limpio, moderno, sin cuadrícula pesada.
 */
export function Backdrop() {
  const ref = useRef<HTMLDivElement | null>(null)
  const frameRef = useRef<number | null>(null)

  useEffect(() => {
    if (window.matchMedia('(hover: none)').matches) return
    const onMove = (e: MouseEvent) => {
      if (frameRef.current !== null) return
      frameRef.current = window.requestAnimationFrame(() => {
        frameRef.current = null
        ref.current?.style.setProperty('--spot-x', `${e.clientX}px`)
        ref.current?.style.setProperty('--spot-y', `${e.clientY}px`)
      })
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onMove)
      if (frameRef.current !== null) window.cancelAnimationFrame(frameRef.current)
    }
  }, [])

  return (
    <div
      ref={ref}
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 bg-paper-100 [--spot-x:-1000px] [--spot-y:-1000px]"
    >
      {/* Dot pattern sutil */}
      <div
        className="absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(124,58,237,0.25) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      {/* Luz que sigue cursor — reveal de dots */}
      <div
        className="absolute inset-0 transition-opacity duration-500"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(124,58,237,0.6) 1px, transparent 1px)',
          backgroundSize: '24px 24px',
          WebkitMaskImage: 'radial-gradient(200px circle at var(--spot-x) var(--spot-y), #000 0%, transparent 70%)',
          maskImage: 'radial-gradient(200px circle at var(--spot-x) var(--spot-y), #000 0%, transparent 70%)',
        }}
      />

      {/* Gradiente superior — glow violeta suave */}
      <motion.div
        className="absolute -top-32 left-1/2 hidden h-[500px] w-[700px] -translate-x-1/2 rounded-full bg-violet-400/15 blur-[120px] sm:block motion-reduce:hidden"
        animate={{ scale: [1, 1.08, 1], opacity: [0.4, 0.6, 0.4] }}
        transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Glow inferior derecho — mint */}
      <motion.div
        className="absolute -bottom-20 -right-20 hidden h-[400px] w-[400px] rounded-full bg-mint-400/10 blur-[100px] sm:block motion-reduce:hidden"
        animate={{ scale: [1, 1.12, 1], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut', delay: 3 }}
      />

      {/* Glow izquierdo — violeta oscuro */}
      <motion.div
        className="absolute -left-32 top-1/2 hidden h-[350px] w-[350px] -translate-y-1/2 rounded-full bg-violet-600/8 blur-[100px] md:block motion-reduce:hidden"
        animate={{ y: [0, 30, 0], opacity: [0.2, 0.4, 0.2] }}
        transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
      />

      {/* Viñeta que suaviza bordes */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_40%,transparent_40%,rgba(252,252,253,.9)_100%)]" />
    </div>
  )
}
