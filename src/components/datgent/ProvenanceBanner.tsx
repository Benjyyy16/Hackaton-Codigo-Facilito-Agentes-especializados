import { cn } from '@/lib/cn'
import type { ProviderInfo } from '@/store/analysisTypes'

interface ProvenanceBannerProps {
  providers: ProviderInfo[]
  isDemoSession: boolean
}

export function ProvenanceBanner({ providers, isDemoSession }: ProvenanceBannerProps) {
  if (providers.length === 0) return null

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-2 rounded-xl border-2 px-4 py-2.5',
        isDemoSession
          ? 'border-clay-300 bg-clay-50'
          : 'border-mint-400 bg-mint-50',
      )}
    >
      {isDemoSession && (
        <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-clay-700">
          SESIÓN DEMO · DATOS SIMULADOS
        </span>
      )}
      {providers.map((p) => (
        <span
          key={p.provider}
          className={cn(
            'rounded border px-2 py-0.5 font-mono text-[9.5px] font-bold uppercase tracking-wider',
            p.connected
              ? 'border-mint-500 bg-mint-100 text-mint-700'
              : 'border-clay-300 bg-clay-50 text-clay-600',
          )}
        >
          {p.label}
        </span>
      ))}
    </div>
  )
}
