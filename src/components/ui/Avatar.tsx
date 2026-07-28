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
  src,
  className,
  ring = true,
}: {
  name: string
  hue?: number
  size?: number
  src?: string | null
  className?: string
  ring?: boolean
}) {
  if (src) {
    return (
      <img
        src={src}
        alt=""
        title={name}
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
        style={{ width: size, height: size }}
        className={cn(
          'inline-block shrink-0 rounded-full bg-paper object-cover',
          ring && 'ring-2 ring-ink-900',
          className,
        )}
      />
    )
  }

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
