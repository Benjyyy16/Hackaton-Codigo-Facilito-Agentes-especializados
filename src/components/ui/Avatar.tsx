import { cn } from '@/lib/cn'

function initials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('')
}

/** Avatar con degradado derivado del nombre. */
export function Avatar({
  name,
  hue = 265,
  size = 36,
  className,
  ring = true,
}: {
  name: string
  hue?: number
  size?: number
  className?: string
  ring?: boolean
}) {
  return (
    <span
      aria-hidden
      title={name}
      style={{
        width: size,
        height: size,
        fontSize: size * 0.36,
        background: `linear-gradient(140deg, hsl(${hue} 66% 62%), hsl(${hue + 32} 58% 42%))`,
      }}
      className={cn(
        'inline-grid shrink-0 place-items-center rounded-full font-bold text-white',
        ring && 'ring-2 ring-ink-900',
        className,
      )}
    >
      {initials(name)}
    </span>
  )
}
