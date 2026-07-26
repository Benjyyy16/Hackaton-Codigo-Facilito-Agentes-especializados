import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

/**
 * Fondo de papel milimetrado. Blanco dominante, con dos capas de cuadrícula
 * y una luz suave que sigue al cursor. Sin gradientes morados de fondo.
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
      {/* cuadrícula fina */}
      <div className="absolute inset-0 bg-grid-fine bg-grid-sm" />
      {/* cuadrícula principal */}
      <div className="absolute inset-0 bg-grid bg-grid" />
      {/* módulos grandes con línea morada tenue */}
      <div
        className="absolute inset-0 bg-grid-lg opacity-70"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(124,58,237,.10) 1px, transparent 1px), linear-gradient(to bottom, rgba(124,58,237,.10) 1px, transparent 1px)',
        }}
      />

      {/* luz que sigue el cursor: revela la cuadrícula en morado */}
      <div
        className="absolute inset-0 transition-opacity duration-300"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(124,58,237,.5) 1px, transparent 1px), linear-gradient(to bottom, rgba(124,58,237,.5) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
          WebkitMaskImage: `radial-gradient(180px circle at ${pos.x}px ${pos.y}px, #000 0%, transparent 72%)`,
          maskImage: `radial-gradient(180px circle at ${pos.x}px ${pos.y}px, #000 0%, transparent 72%)`,
        }}
      />

      {/* viñeta que aclara los bordes */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_35%,transparent_35%,rgba(252,252,253,.85)_100%)]" />

      {/* dos manchas morado/verde muy tenues para que el blanco no sea plano */}
      <motion.div
        className="absolute -left-40 top-24 h-[420px] w-[420px] rounded-full bg-violet-300/20 blur-[130px]"
        animate={{ y: [0, 50, 0], opacity: [0.5, 0.8, 0.5] }}
        transition={{ duration: 19, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute -right-32 top-[58%] h-[360px] w-[360px] rounded-full bg-mint-300/20 blur-[130px]"
        animate={{ y: [0, -44, 0], opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 23, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
      />
    </div>
  )
}
