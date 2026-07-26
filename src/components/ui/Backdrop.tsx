import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

/**
 * Fondo minimalista con dots sutiles y gradientes suaves.
 * Inspirado en aguilarb.tech: limpio, moderno, sin cuadrícula pesada.
 */
export function Backdrop() {
  const [pos, setPos] = useState({ x: -1000, y: -1000 })

  useEffect(() => {
    if (window.matchMedia('(hover: none)').matches) return
    const onMove = (e: MouseEvent) => setPos({ x: e.clientX, y: e.clientY })
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => window.removeEventListener('pointermove', onMove)
  }, [])

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 bg-paper-100">
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
          WebkitMaskImage: `radial-gradient(200px circle at ${pos.x}px ${pos.y}px, #000 0%, transparent 70%)`,
          maskImage: `radial-gradient(200px circle at ${pos.x}px ${pos.y}px, #000 0%, transparent 70%)`,
        }}
      />

      {/* Gradiente superior — glow violeta suave */}
      <motion.div
        className="absolute -top-32 left-1/2 h-[500px] w-[700px] -translate-x-1/2 rounded-full bg-violet-400/15 blur-[120px]"
        animate={{ scale: [1, 1.08, 1], opacity: [0.4, 0.6, 0.4] }}
        transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Glow inferior derecho — mint */}
      <motion.div
        className="absolute -bottom-20 -right-20 h-[400px] w-[400px] rounded-full bg-mint-400/10 blur-[100px]"
        animate={{ scale: [1, 1.12, 1], opacity: [0.3, 0.5, 0.3] }}
        transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut', delay: 3 }}
      />

      {/* Glow izquierdo — violeta oscuro */}
      <motion.div
        className="absolute -left-32 top-1/2 h-[350px] w-[350px] -translate-y-1/2 rounded-full bg-violet-600/8 blur-[100px]"
        animate={{ y: [0, 30, 0], opacity: [0.2, 0.4, 0.2] }}
        transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
      />

      {/* Viñeta que suaviza bordes */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_40%,transparent_40%,rgba(252,252,253,.9)_100%)]" />
    </div>
  )
}
