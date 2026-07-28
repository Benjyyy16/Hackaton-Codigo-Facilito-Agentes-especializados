import { motion } from 'framer-motion'
import { Brain, Compass, FileText, LineChart, ShieldCheck, Code2 } from 'lucide-react'
import {
  CodigoFacilitoLogo,
  GitHubLogo,
  KiroLogo,
  OrquestaMark,
  SupabaseLogo,
} from '@/components/brand/Logos'

/**
 * Esquema de conexión estilo plano de ingeniería: los agentes son módulos
 * cableados a un bus central. Sin glow: líneas, cotas y anotaciones.
 */

const agents = [
  { icon: Brain, name: 'Estratega', code: 'AG-01', side: 'l' as const, row: 0 },
  { icon: Code2, name: 'Arquitecto', code: 'AG-02', side: 'l' as const, row: 1 },
  { icon: Compass, name: 'Constructor', code: 'AG-03', side: 'l' as const, row: 2 },
  { icon: ShieldCheck, name: 'Auditor', code: 'AG-04', side: 'r' as const, row: 0 },
  { icon: LineChart, name: 'Analista', code: 'AG-05', side: 'r' as const, row: 1 },
  { icon: FileText, name: 'Cronista', code: 'AG-06', side: 'r' as const, row: 2 },
]

export function AgentBlueprint() {
  return (
    <div className="relative mx-auto w-full max-w-[520px]">
      {/* marco de plano con cotas */}
      <div className="relative rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard-lg sm:p-6">
        {/* cabecera del plano */}
        <div className="mb-5 flex items-end justify-between border-b-2 border-dashed border-ink-200 pb-3">
          <div>
            <p className="label-mono text-ink-400">Esquema</p>
            <p className="font-display text-[19px] leading-none text-ink-900">
              Bus de orquestación
            </p>
          </div>
          <div className="text-right">
            <p className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">esc. 1:1</p>
            <p className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">rev. 07</p>
          </div>
        </div>

        <div className="relative grid grid-cols-[1fr_auto_1fr] items-center gap-x-2 gap-y-3">
          {/* ---- columna izquierda ---- */}
          <div className="space-y-3">
            {agents
              .filter((a) => a.side === 'l')
              .map((a, i) => (
                <AgentChip key={a.code} {...a} delay={0.5 + i * 0.12} align="right" />
              ))}
          </div>

          {/* ---- bus central ---- */}
          <div className="relative flex h-full flex-col items-center justify-center px-1">
            {/* riel vertical */}
            <div className="absolute inset-y-0 left-1/2 w-[3px] -translate-x-1/2 bg-ink-900" />
            {/* señal que recorre el bus */}
            <motion.div
              className="absolute left-1/2 h-8 w-[3px] -translate-x-1/2 bg-mint-500"
              animate={{ top: ['-8%', '100%'] }}
              transition={{ duration: 2.6, repeat: Infinity, ease: 'linear' }}
            />

            {/* núcleo */}
            <motion.div
              initial={{ scale: 0, rotate: -25 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ delay: 0.28, type: 'spring', stiffness: 220, damping: 15 }}
              className="relative z-10 rounded-xl border-2 border-ink-900 bg-violet-600 p-3 shadow-hard"
            >
              <div className="flex items-center gap-1.5">
                <GitHubLogo className="h-[18px] w-[18px] text-white" />
                <span className="h-4 w-px bg-white/35" />
                <SupabaseLogo className="h-[18px] w-[18px]" />
              </div>
              <p className="mt-1.5 whitespace-nowrap text-center font-mono text-[8.5px] font-bold uppercase tracking-[0.12em] text-white">
                fuente de verdad
              </p>
              {/* pulso de anillo cuadrado */}
              <motion.span
                aria-hidden
                className="absolute inset-0 rounded-xl border-2 border-violet-600"
                animate={{ scale: [1, 1.45], opacity: [0.7, 0] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: 'easeOut' }}
              />
            </motion.div>
          </div>

          {/* ---- columna derecha ---- */}
          <div className="space-y-3">
            {agents
              .filter((a) => a.side === 'r')
              .map((a, i) => (
                <AgentChip key={a.code} {...a} delay={0.56 + i * 0.12} align="left" />
              ))}
          </div>
        </div>

        {/* pie del plano: cota horizontal */}
        <div className="mt-5 border-t-2 border-dashed border-ink-200 pt-3">
          <div className="flex items-center gap-2">
            <span className="h-2 w-px bg-ink-300" />
            <div className="relative h-px flex-1 bg-ink-300">
              <motion.span
                className="absolute -top-[3px] h-[7px] w-[7px] rounded-full bg-violet-600"
                animate={{ left: ['0%', '100%'] }}
                transition={{ duration: 3.4, repeat: Infinity, ease: 'easeInOut' }}
              />
            </div>
            <span className="h-2 w-px bg-ink-300" />
            <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
              latencia media 1.8 s
            </span>
          </div>
        </div>
      </div>

      {/* anotación manuscrita */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 1.5 }}
        className="mt-3 flex items-start gap-2 pl-6"
      >
        <svg viewBox="0 0 40 30" className="mt-0.5 h-6 w-8 shrink-0 text-ink-300">
          <path
            d="M38 2C22 4 8 10 4 26M4 26l7-5M4 26l1-8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
        <p className="max-w-[260px] font-display text-[14px] italic leading-snug text-ink-500">
          Ningún agente escribe en main sin pasar por rebiew y aprobación humana.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 1.65 }}
        className="mt-4 rounded-xl border-2 border-ink-900 bg-paper px-4 py-3 shadow-hard-sm"
      >
        <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink-400">
          creada por
        </p>
        <p className="mt-1 text-[13px] font-extrabold leading-snug text-ink-900">
          Benjamin Aguilar, Tomas Hernandez, Ramon Molina
        </p>
        <div className="mt-3 flex items-center gap-2">
          <OrquestaMark className="h-8 w-8" />
          <CodigoFacilitoLogo className="h-8 w-8" />
          <KiroLogo className="h-8 w-8" />
        </div>
      </motion.div>
    </div>
  )
}

function AgentChip({
  icon: Icon,
  name,
  code,
  delay,
  align,
}: {
  icon: React.ElementType
  name: string
  code: string
  delay: number
  align: 'left' | 'right'
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: align === 'right' ? -22 : 22 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay, duration: 0.5, ease: [0.19, 1, 0.22, 1] }}
      className={`group flex items-center gap-2 ${align === 'right' ? 'flex-row' : 'flex-row-reverse'}`}
    >
      <div className="min-w-0 flex-1 rounded-lg border-2 border-ink-900 bg-paper px-2.5 py-2 transition-colors group-hover:bg-violet-50">
        <div
          className={`flex items-center gap-2 ${align === 'left' ? 'flex-row-reverse text-right' : ''}`}
        >
          <Icon className="h-3.5 w-3.5 shrink-0 text-violet-600" />
          <div className="min-w-0">
            <p className="truncate text-[12px] font-bold leading-tight text-ink-900">{name}</p>
            <p className="font-mono text-[8.5px] uppercase tracking-wider text-ink-400">{code}</p>
          </div>
        </div>
      </div>
      {/* cable al bus */}
      <div className="flex shrink-0 items-center">
        <span className="h-[2px] w-4 bg-ink-900" />
        <span className="h-[7px] w-[7px] rotate-45 border-2 border-ink-900 bg-mint-500" />
      </div>
    </motion.div>
  )
}
