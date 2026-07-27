import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type CSSProperties,
} from 'react'
import { motion, useInView, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { cn } from '@/lib/cn'

/* ================================================================== */
/* Sello: entra girando y golpeando, como un timbre de papel           */
/* ================================================================== */

export function Stamp({
  children,
  tone = 'mint',
  className,
  delay = 0,
}: {
  children: ReactNode
  tone?: 'mint' | 'violet' | 'clay' | 'ink'
  className?: string
  delay?: number
}) {
  const tones = {
    mint: 'border-mint-600 text-mint-700 bg-mint-50',
    violet: 'border-violet-600 text-violet-700 bg-violet-50',
    clay: 'border-clay-500 text-clay-700 bg-clay-100',
    ink: 'border-ink-900 text-ink-900 bg-paper',
  }
  return (
    <motion.span
      initial={{ scale: 2.3, rotate: -20, opacity: 0 }}
      whileInView={{ scale: 1, rotate: -7, opacity: 1 }}
      viewport={{ once: true, amount: 0.8 }}
      transition={{ type: 'spring', stiffness: 260, damping: 13, delay }}
      className={cn('stamp', tones[tone], className)}
    >
      {children}
    </motion.span>
  )
}

/* ================================================================== */
/* Marquee: cinta infinita de texto                                    */
/* ================================================================== */

export function Marquee({
  items,
  reverse,
  className,
  itemClassName,
}: {
  items: ReactNode[]
  reverse?: boolean
  className?: string
  itemClassName?: string
}) {
  const doubled = [...items, ...items]
  return (
    <div className={cn('mask-fade-x overflow-hidden', className)}>
      <div
        className={cn(
          'flex w-max items-center',
          reverse ? 'animate-marquee-rev' : 'animate-marquee',
        )}
      >
        {doubled.map((it, i) => (
          <span key={i} className={cn('flex shrink-0 items-center', itemClassName)}>
            {it}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ================================================================== */
/* Odómetro: dígitos que ruedan verticalmente                          */
/* ================================================================== */

function Digit({ target, delay }: { target: number; delay: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.6 })
  return (
    <span ref={ref} className="relative inline-block h-[1em] w-[0.62em] overflow-hidden align-baseline">
      <motion.span
        className="absolute left-0 top-0 flex flex-col items-center"
        animate={{ y: inView ? `-${target}em` : '0em' }}
        transition={{ duration: 1.1, delay, ease: [0.16, 1, 0.3, 1] }}
      >
        {Array.from({ length: 10 }, (_, n) => (
          <span key={n} className="flex h-[1em] items-center justify-center leading-none">
            {n}
          </span>
        ))}
      </motion.span>
    </span>
  )
}

/** Anima solo los dígitos, preservando símbolos como % + – */
export function Odometer({ value, className }: { value: string; className?: string }) {
  let digitIndex = 0
  return (
    <span className={cn('inline-flex items-baseline tabular-nums', className)}>
      {value.split('').map((ch, i) =>
        /\d/.test(ch) ? (
          <Digit key={i} target={Number(ch)} delay={digitIndex++ * 0.08} />
        ) : (
          <span key={i}>{ch}</span>
        ),
      )}
    </span>
  )
}

/* ================================================================== */
/* Tilt 3D: la tarjeta se inclina siguiendo el cursor                  */
/* ================================================================== */

export function Tilt({
  children,
  className,
  strength = 9,
}: {
  children: ReactNode
  className?: string
  strength?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const rx = useSpring(useTransform(my, [-0.5, 0.5], [strength, -strength]), {
    stiffness: 240,
    damping: 22,
  })
  const ry = useSpring(useTransform(mx, [-0.5, 0.5], [-strength, strength]), {
    stiffness: 240,
    damping: 22,
  })

  return (
    <motion.div
      ref={ref}
      onMouseMove={(e) => {
        const r = ref.current?.getBoundingClientRect()
        if (!r) return
        mx.set((e.clientX - r.left) / r.width - 0.5)
        my.set((e.clientY - r.top) / r.height - 0.5)
      }}
      onMouseLeave={() => {
        mx.set(0)
        my.set(0)
      }}
      style={{ rotateX: rx, rotateY: ry, transformPerspective: 900 }}
      className={cn('preserve-3d', className)}
    >
      {children}
    </motion.div>
  )
}

/* ================================================================== */
/* Máquina de escribir con cursor                                      */
/* ================================================================== */

export function Typewriter({
  lines,
  className,
  speed = 32,
  holdMs = 1700,
}: {
  lines: string[]
  className?: string
  speed?: number
  holdMs?: number
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { amount: 0.6 })
  const [text, setText] = useState('')
  const [line, setLine] = useState(0)

  /**
   * `lines` suele venir como literal en el JSX, así que su identidad cambia en
   * cada render del padre. Dependiendo del array se reiniciaba la animación una
   * y otra vez; se depende del contenido y el valor se lee de un ref.
   */
  const linesKey = lines.join('\u0000')
  const linesRef = useRef(lines)
  useEffect(() => {
    linesRef.current = lines
  }, [lines])

  useEffect(() => {
    if (!inView) return
    const all = linesRef.current
    if (all.length === 0) return
    const full = all[line % all.length]
    let i = 0
    let hold: number | undefined
    let erase: number | undefined

    const type = window.setInterval(() => {
      i += 1
      setText(full.slice(0, i))
      if (i >= full.length) {
        window.clearInterval(type)
        hold = window.setTimeout(() => {
          let j = full.length
          erase = window.setInterval(() => {
            j -= 2
            setText(full.slice(0, Math.max(j, 0)))
            if (j <= 0) {
              window.clearInterval(erase)
              setLine((l) => l + 1)
            }
          }, 14)
        }, holdMs)
      }
    }, speed)

    return () => {
      window.clearInterval(type)
      if (hold) window.clearTimeout(hold)
      if (erase) window.clearInterval(erase)
    }
  }, [inView, line, linesKey, speed, holdMs])

  return (
    <span ref={ref} className={className}>
      {text}
      <span className="ml-0.5 inline-block w-[0.55em] animate-blink bg-violet-600 align-baseline">
        &nbsp;
      </span>
    </span>
  )
}

/* ================================================================== */
/* Texto que se descifra al hacer hover                                */
/* ================================================================== */

const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ#$%&/*+<>[]{}'

export function ScrambleText({
  text,
  className,
  as: Tag = 'span',
}: {
  text: string
  className?: string
  as?: 'span' | 'h3' | 'p'
}) {
  const [out, setOut] = useState(text)
  const raf = useRef<number>()

  function run() {
    let frame = 0
    cancelAnimationFrame(raf.current ?? 0)
    const tick = () => {
      frame += 1
      setOut(
        text
          .split('')
          .map((c, i) => {
            if (c === ' ') return ' '
            if (i < frame / 2.2) return text[i]
            return GLYPHS[Math.floor(Math.random() * GLYPHS.length)]
          })
          .join(''),
      )
      if (frame / 2.2 < text.length) raf.current = requestAnimationFrame(tick)
      else setOut(text)
    }
    raf.current = requestAnimationFrame(tick)
  }

  useEffect(() => () => cancelAnimationFrame(raf.current ?? 0), [])

  return (
    <Tag onMouseEnter={run} className={cn('font-mono', className)}>
      {out}
    </Tag>
  )
}

/* ================================================================== */
/* Anotación: subrayado / círculo dibujado a mano                      */
/* ================================================================== */

export function Scribble({
  variant = 'underline',
  className,
  delay = 0.2,
  color = '#7C3AED',
}: {
  variant?: 'underline' | 'circle' | 'strike' | 'zigzag'
  className?: string
  delay?: number
  color?: string
}) {
  const paths = {
    underline: { d: 'M3 9C70 3.5 152 3 297 7.5', box: '0 0 300 12' },
    strike: { d: 'M2 7C68 4 150 10 298 5', box: '0 0 300 12' },
    zigzag: { d: 'M2 8l24-5 24 5 24-5 24 5 24-5 24 5 24-5 24 5 24-5 24 5 24-5', box: '0 0 300 14' },
    circle: {
      d: 'M148 4C74 4 8 18 8 34c0 17 70 30 142 30s140-13 140-30C290 18 224 4 148 4',
      box: '0 0 300 70',
    },
  }
  const p = paths[variant]
  return (
    <motion.svg
      aria-hidden
      viewBox={p.box}
      preserveAspectRatio="none"
      className={cn('pointer-events-none absolute', className)}
      initial="hidden"
      whileInView="shown"
      viewport={{ once: true, amount: 0.7 }}
    >
      <motion.path
        d={p.d}
        fill="none"
        stroke={color}
        strokeWidth={variant === 'circle' ? 3 : 4}
        strokeLinecap="round"
        variants={{ hidden: { pathLength: 0 }, shown: { pathLength: 1 } }}
        transition={{ duration: 0.75, delay, ease: 'easeInOut' }}
      />
    </motion.svg>
  )
}

/* ================================================================== */
/* Contenedor con aparición al hacer scroll                            */
/* ================================================================== */

type Dir = 'up' | 'down' | 'left' | 'right' | 'scale' | 'skew'

const from: Record<Dir, Record<string, number | string>> = {
  up: { y: 28 },
  down: { y: -28 },
  left: { x: 34 },
  right: { x: -34 },
  scale: { scale: 0.93 },
  skew: { y: 22, skewY: 3 },
}

export function Reveal({
  children,
  className,
  delay = 0,
  direction = 'up',
  duration = 0.62,
  amount = 0.25,
  style,
}: {
  children: ReactNode
  className?: string
  delay?: number
  direction?: Dir
  duration?: number
  amount?: number
  style?: CSSProperties
}) {
  return (
    <motion.div
      className={className}
      style={style}
      initial={{ opacity: 0, ...from[direction] }}
      whileInView={{ opacity: 1, x: 0, y: 0, scale: 1, skewY: 0 }}
      viewport={{ once: true, amount }}
      transition={{ duration, delay, ease: [0.19, 1, 0.22, 1] }}
    >
      {children}
    </motion.div>
  )
}

export function Stagger({
  children,
  className,
  amount = 0.18,
  gap = 0.075,
}: {
  children: ReactNode
  className?: string
  amount?: number
  gap?: number
}) {
  return (
    <motion.div
      className={className}
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap } } }}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, amount }}
    >
      {children}
    </motion.div>
  )
}

export function StaggerItem({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 26 },
        show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.19, 1, 0.22, 1] } },
      }}
      className={className}
    >
      {children}
    </motion.div>
  )
}

/** Título que entra palabra por palabra desde abajo. */
export function WordsReveal({
  text,
  className,
  wordClassName,
  delay = 0,
}: {
  text: string
  className?: string
  wordClassName?: string
  delay?: number
}) {
  const words = text.split(' ')
  return (
    <span className={cn('inline-flex flex-wrap', className)}>
      {words.map((w, i) => (
        <span key={`${w}-${i}`} className="inline-block overflow-hidden py-[0.05em]">
          <motion.span
            className={cn('inline-block', wordClassName)}
            initial={{ y: '110%', opacity: 0, rotate: 4 }}
            animate={{ y: '0%', opacity: 1, rotate: 0 }}
            transition={{ duration: 0.8, delay: delay + i * 0.06, ease: [0.19, 1, 0.22, 1] }}
          >
            {w}
            {i < words.length - 1 && '\u00A0'}
          </motion.span>
        </span>
      ))}
    </span>
  )
}
