import { cn } from '@/lib/cn'

/** Bloque gris pulsante para reservar el espacio del contenido que carga. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn('block animate-pulse rounded-lg bg-ink-100', className)}
    />
  )
}

/** Fila que imita una tarjeta de repositorio de `RepoSelector`. */
export function RepoRowSkeleton() {
  return (
    <div className="rounded-xl border-2 border-ink-200 bg-paper p-4">
      <div className="flex items-start gap-3">
        <Skeleton className="h-8 w-8 shrink-0 rounded-lg" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-3.5 w-1/2" />
          <Skeleton className="h-3 w-3/4" />
          <div className="flex gap-2 pt-0.5">
            <Skeleton className="h-3 w-14" />
            <Skeleton className="h-3 w-10" />
          </div>
        </div>
        <Skeleton className="h-9 w-24 shrink-0 rounded-lg" />
      </div>
    </div>
  )
}

/** Tarjeta placeholder para las grillas de proyectos y de agentes. */
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-xl border-2 border-ink-200 bg-paper p-5', className)}>
      <Skeleton className="h-4 w-2/5" />
      <Skeleton className="mt-3 h-3 w-full" />
      <Skeleton className="mt-1.5 h-3 w-4/5" />
      <Skeleton className="mt-5 h-2.5 w-full rounded" />
    </div>
  )
}

/**
 * Envoltorio accesible para estados de carga: anuncia el progreso a lectores
 * de pantalla y oculta los placeholders visuales de ellos.
 */
export function LoadingRegion({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <div role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      {children}
    </div>
  )
}
