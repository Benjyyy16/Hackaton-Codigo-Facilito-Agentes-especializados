import { motion } from 'framer-motion'
import { cn } from '@/lib/cn'
import type { WsConnectionState } from '@/store/analysisTypes'

interface WsIndicatorProps {
  state: WsConnectionState
}

const labels: Record<WsConnectionState, string> = {
  live: 'En vivo',
  reconnecting: 'Reconectando',
  disconnected: 'Desconectado',
}

const dot: Record<WsConnectionState, string> = {
  live: 'bg-mint-500',
  reconnecting: 'bg-clay-500',
  disconnected: 'bg-ink-400',
}

const text: Record<WsConnectionState, string> = {
  live: 'text-mint-700',
  reconnecting: 'text-clay-700',
  disconnected: 'text-ink-500',
}

export function WsIndicator({ state }: WsIndicatorProps) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative flex h-2 w-2">
        {state === 'live' && (
          <motion.span
            className={cn('absolute inline-flex h-full w-full rounded-full opacity-75', dot[state])}
            animate={{ scale: [1, 1.8, 1], opacity: [0.75, 0, 0.75] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
        )}
        <span className={cn('relative inline-flex h-2 w-2 rounded-full', dot[state])} />
      </span>
      <span className={cn('font-mono text-[10px] font-bold uppercase tracking-wider', text[state])}>
        {labels[state]}
      </span>
    </span>
  )
}
