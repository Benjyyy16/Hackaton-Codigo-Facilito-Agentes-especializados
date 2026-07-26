import { forwardRef, useRef, useState, type ReactNode } from 'react'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { cn } from '@/lib/cn'

type Variant = 'primary' | 'ink' | 'mint' | 'outline' | 'ghost' | 'paper'
type Size = 'sm' | 'md' | 'lg'

/**
 * Botones con borde duro y sombra desplazada: al presionar, la sombra
 * colapsa y el botón "se hunde" (feedback físico, no glow).
 */
const variants: Record<Variant, string> = {
  primary: 'border-ink-900 bg-violet-600 text-white',
  ink: 'border-ink-900 bg-ink-900 text-white',
  mint: 'border-ink-900 bg-mint-500 text-ink-900',
  paper: 'border-ink-900 bg-paper text-ink-900',
  outline: 'border-ink-300 bg-paper text-ink-800 shadow-none hover:border-ink-900',
  ghost: 'border-transparent bg-transparent text-ink-700 shadow-none hover:bg-ink-100',
}

const withShadow: Record<Variant, boolean> = {
  primary: true,
  ink: true,
  mint: true,
  paper: true,
  outline: false,
  ghost: false,
}

const sizes: Record<Size, string> = {
  sm: 'h-9 px-3.5 text-[13px] gap-1.5 rounded-lg border-2',
  md: 'h-11 px-5 text-[14px] gap-2 rounded-[10px] border-2',
  lg: 'h-[54px] px-7 text-[15px] gap-2.5 rounded-xl border-2',
}

export interface ButtonProps extends Omit<HTMLMotionProps<'button'>, 'children'> {
  variant?: Variant
  size?: Size
  loading?: boolean
  fullWidth?: boolean
  /** El botón se inclina hacia el cursor */
  magnetic?: boolean
  children?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    className,
    variant = 'primary',
    size = 'md',
    loading,
    fullWidth,
    magnetic = true,
    children,
    disabled,
    ...props
  },
  ref,
) {
  const local = useRef<HTMLButtonElement | null>(null)
  const [tug, setTug] = useState({ x: 0, y: 0 })
  const inert = disabled || loading
  const hasShadow = withShadow[variant]

  return (
    <motion.button
      ref={(node) => {
        local.current = node
        if (typeof ref === 'function') ref(node)
        else if (ref) ref.current = node
      }}
      onMouseMove={(e) => {
        if (!magnetic || inert) return
        const r = local.current?.getBoundingClientRect()
        if (!r) return
        setTug({
          x: ((e.clientX - (r.left + r.width / 2)) / r.width) * 7,
          y: ((e.clientY - (r.top + r.height / 2)) / r.height) * 5,
        })
      }}
      onMouseLeave={() => setTug({ x: 0, y: 0 })}
      animate={{ x: tug.x, y: tug.y }}
      whileHover={inert ? undefined : { scale: 1.015 }}
      whileTap={inert ? undefined : { scale: 0.97, x: 3, y: 3 }}
      transition={{ type: 'spring', stiffness: 340, damping: 22, mass: 0.4 }}
      disabled={inert}
      className={cn(
        'group relative inline-flex select-none items-center justify-center overflow-hidden whitespace-nowrap font-semibold',
        'transition-shadow duration-150',
        hasShadow && 'shadow-hard active:shadow-none',
        variants[variant],
        sizes[size],
        fullWidth && 'w-full',
        inert && 'cursor-not-allowed opacity-55',
        className,
      )}
      {...props}
    >
      {/* destello diagonal al pasar el cursor */}
      {!inert && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]"
        >
          <span className="absolute inset-y-0 -left-full w-1/3 bg-white/25 blur-[2px] transition-transform duration-500 ease-out group-hover:animate-sheen-x" />
        </span>
      )}
      {loading && (
        <span
          aria-hidden
          className="mr-1.5 h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      <span className="relative z-10 inline-flex items-center gap-2">{children}</span>
    </motion.button>
  )
})
