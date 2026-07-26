import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { Reveal } from './Bits'

/** Encabezado de sección con índice numérico tipo especificación técnica. */
export function SectionHeading({
  index,
  eyebrow,
  title,
  subtitle,
  align = 'center',
  className,
}: {
  index?: string
  eyebrow?: string
  title: ReactNode
  subtitle?: ReactNode
  align?: 'center' | 'left'
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4',
        align === 'center' ? 'items-center text-center' : 'items-start text-left',
        className,
      )}
    >
      {(eyebrow || index) && (
        <Reveal direction="scale">
          <span className="inline-flex items-center gap-2.5">
            {index && (
              <span className="grid h-6 min-w-6 place-items-center rounded border-2 border-ink-900 bg-ink-900 px-1 font-mono text-[10px] font-bold text-white">
                {index}
              </span>
            )}
            {eyebrow && <span className="label-mono text-violet-700">{eyebrow}</span>}
            <span className="h-px w-8 bg-ink-300" />
          </span>
        </Reveal>
      )}

      <Reveal delay={0.05}>
        <h2
          className={cn(
            'text-balance font-display text-[32px] leading-[1.05] tracking-tightest text-ink-900 sm:text-[42px] lg:text-[48px]',
            align === 'center' ? 'max-w-3xl' : 'max-w-2xl',
          )}
        >
          {title}
        </h2>
      </Reveal>

      {subtitle && (
        <Reveal delay={0.11}>
          <p
            className={cn(
              'text-pretty text-[15.5px] leading-[1.65] text-ink-600',
              align === 'center' ? 'mx-auto max-w-2xl' : 'max-w-xl',
            )}
          >
            {subtitle}
          </p>
        </Reveal>
      )}
    </div>
  )
}
