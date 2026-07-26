import { motion } from 'framer-motion'
import {
  Brain,
  Database,
  FileText,
  GitMerge,
  LayoutDashboard,
  LineChart,
  ShieldCheck,
} from 'lucide-react'
import { GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'

/**
 * Diagrama de recorrido de un cambio, dibujado como plano:
 * líneas ortogonales, nodos con borde duro y pulsos de señal.
 */

type NodeDef = {
  id: string
  x: number
  y: number
  w: number
  h: number
  label: string
  sub?: string
  kind: 'source' | 'agent' | 'board' | 'output'
}

const N: NodeDef[] = [
  { id: 'gh', x: 6, y: 64, w: 130, h: 54, label: 'GitHub', sub: 'commits · PRs · CI', kind: 'source' },
  { id: 'sb', x: 6, y: 152, w: 130, h: 54, label: 'Supabase', sub: 'schema · RLS', kind: 'source' },

  { id: 'plan', x: 208, y: 20, w: 134, h: 50, label: 'Estratega', sub: 'prioriza', kind: 'agent' },
  { id: 'audit', x: 208, y: 96, w: 134, h: 50, label: 'Auditor', sub: 'valida', kind: 'agent' },
  { id: 'doc', x: 208, y: 172, w: 134, h: 50, label: 'Cronista', sub: 'documenta', kind: 'agent' },
  { id: 'fin', x: 208, y: 248, w: 134, h: 50, label: 'Analista', sub: 'costea', kind: 'agent' },

  { id: 'board', x: 414, y: 98, w: 148, h: 80, label: 'Canvas', sub: 'tarjetas vivas', kind: 'board' },

  { id: 'merge', x: 634, y: 36, w: 136, h: 50, label: 'Merge a main', sub: 'con aprobación', kind: 'output' },
  { id: 'report', x: 634, y: 112, w: 136, h: 50, label: 'Reporte', sub: 'con evidencia', kind: 'output' },
  { id: 'cost', x: 634, y: 188, w: 136, h: 50, label: 'Costo/feature', sub: 'trazable', kind: 'output' },
]

const E: { from: string; to: string; accent?: boolean; delay: number }[] = [
  { from: 'gh', to: 'plan', delay: 0 },
  { from: 'gh', to: 'audit', accent: true, delay: 0.35 },
  { from: 'gh', to: 'doc', delay: 0.7 },
  { from: 'sb', to: 'audit', delay: 1.05 },
  { from: 'sb', to: 'fin', delay: 1.4 },
  { from: 'plan', to: 'board', delay: 0.5 },
  { from: 'audit', to: 'board', accent: true, delay: 0.85 },
  { from: 'doc', to: 'board', delay: 1.2 },
  { from: 'fin', to: 'board', delay: 1.55 },
  { from: 'board', to: 'merge', accent: true, delay: 0.6 },
  { from: 'board', to: 'report', delay: 0.95 },
  { from: 'board', to: 'cost', delay: 1.3 },
]

const icons: Record<string, React.ElementType> = {
  plan: Brain,
  audit: ShieldCheck,
  doc: FileText,
  fin: LineChart,
  board: LayoutDashboard,
  merge: GitMerge,
  report: FileText,
  cost: LineChart,
  sb: Database,
}

const byId = (id: string) => N.find((n) => n.id === id)!

/** Ruta ortogonal (estilo circuito) del borde derecho de A al izquierdo de B. */
function orthPath(a: NodeDef, b: NodeDef) {
  const x1 = a.x + a.w
  const y1 = a.y + a.h / 2
  const x2 = b.x
  const y2 = b.y + b.h / 2
  const mid = x1 + (x2 - x1) / 2
  const r = 7
  if (Math.abs(y1 - y2) < 2) return `M ${x1} ${y1} H ${x2}`
  const dir = y2 > y1 ? 1 : -1
  return [
    `M ${x1} ${y1}`,
    `H ${mid - r}`,
    `Q ${mid} ${y1} ${mid} ${y1 + r * dir}`,
    `V ${y2 - r * dir}`,
    `Q ${mid} ${y2} ${mid + r} ${y2}`,
    `H ${x2}`,
  ].join(' ')
}

const kindStyle: Record<NodeDef['kind'], string> = {
  source: 'border-ink-900 bg-paper',
  agent: 'border-ink-900 bg-violet-50',
  board: 'border-ink-900 bg-mint-100',
  output: 'border-ink-900 bg-paper-100',
}

export function FlowDiagram() {
  return (
    <div>
      {/* leyenda */}
      <div className="mb-5 flex flex-wrap items-center gap-x-6 gap-y-2">
        {[
          { c: 'bg-paper border-ink-900', t: 'Fuentes' },
          { c: 'bg-violet-50 border-ink-900', t: 'Agentes' },
          { c: 'bg-mint-100 border-ink-900', t: 'Canvas' },
          { c: 'bg-paper-100 border-ink-900', t: 'Salidas' },
        ].map((l) => (
          <span key={l.t} className="label-mono flex items-center gap-2 text-ink-500">
            <span className={`h-3 w-3 border-2 ${l.c}`} />
            {l.t}
          </span>
        ))}
      </div>

      <div className="overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard-lg">
        {/* cabecera del plano */}
        <div className="flex items-center justify-between border-b-2 border-ink-900 bg-ink-900 px-4 py-2">
          <span className="font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-white">
            recorrido de un cambio
          </span>
          <span className="font-mono text-[9.5px] uppercase tracking-wider text-white/45">
            dwg-04
          </span>
        </div>

        <div className="overflow-x-auto bg-grid-fine bg-grid-sm p-4">
          <div className="relative mx-auto h-[318px] w-[790px]">
            <svg
              aria-hidden
              viewBox="0 0 790 318"
              className="absolute inset-0 h-full w-full"
              fill="none"
            >
              <defs>
                <marker
                  id="fd-tip"
                  viewBox="0 0 8 8"
                  refX="6.5"
                  refY="4"
                  markerWidth="5"
                  markerHeight="5"
                  orient="auto"
                >
                  <path d="M0 0 L8 4 L0 8 z" fill="#0D0B16" />
                </marker>
              </defs>

              {E.map((e, i) => {
                const d = orthPath(byId(e.from), byId(e.to))
                return (
                  <g key={i}>
                    <motion.path
                      d={d}
                      stroke={e.accent ? '#7C3AED' : '#BDB8CC'}
                      strokeWidth={e.accent ? 2 : 1.5}
                      markerEnd="url(#fd-tip)"
                      initial={{ pathLength: 0 }}
                      whileInView={{ pathLength: 1 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.85, delay: e.delay * 0.3, ease: 'easeInOut' }}
                    />
                    {/* señal cuadrada que recorre la línea */}
                    <rect
                      width="6"
                      height="6"
                      y="-3"
                      fill={e.accent ? '#3ECF8E' : '#7C3AED'}
                      stroke="#0D0B16"
                      strokeWidth="1"
                      opacity="0"
                    >
                      <animateMotion
                        dur="3.6s"
                        repeatCount="indefinite"
                        begin={`${e.delay}s`}
                        path={d}
                        keyPoints="0;1"
                        keyTimes="0;0.6"
                        calcMode="linear"
                      />
                      <animate
                        attributeName="opacity"
                        dur="3.6s"
                        repeatCount="indefinite"
                        begin={`${e.delay}s`}
                        values="0;1;1;0;0"
                        keyTimes="0;0.06;0.52;0.6;1"
                      />
                    </rect>
                  </g>
                )
              })}
            </svg>

            {/* nodos */}
            {N.map((n, i) => {
              const Icon = icons[n.id]
              return (
                <motion.div
                  key={n.id}
                  className={`absolute flex flex-col justify-center rounded-lg border-2 px-2.5 shadow-hard-sm ${kindStyle[n.kind]}`}
                  style={{ left: n.x, top: n.y, width: n.w, height: n.h }}
                  initial={{ opacity: 0, scale: 0.86, y: 8 }}
                  whileInView={{ opacity: 1, scale: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: i * 0.055, type: 'spring', stiffness: 260, damping: 20 }}
                >
                  <div className="flex items-center gap-1.5">
                    {n.id === 'gh' ? (
                      <GitHubLogo className="h-3.5 w-3.5 shrink-0 text-ink-900" />
                    ) : n.id === 'sb' ? (
                      <SupabaseLogo className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      Icon && <Icon className="h-3.5 w-3.5 shrink-0 text-violet-600" />
                    )}
                    <span className="truncate text-[12px] font-bold text-ink-900">{n.label}</span>
                  </div>
                  {n.sub && (
                    <span className="mt-0.5 truncate pl-5 font-mono text-[9.5px] text-ink-400">
                      {n.sub}
                    </span>
                  )}
                  {n.kind === 'board' && (
                    <motion.span
                      className="absolute -right-1.5 -top-1.5 h-3 w-3 border-2 border-ink-900 bg-mint-500"
                      animate={{ rotate: [0, 90, 180, 270, 360] }}
                      transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
                    />
                  )}
                </motion.div>
              )
            })}
          </div>
        </div>

        {/* pie: bucle de retroalimentación */}
        <div className="flex items-center gap-2.5 border-t-2 border-ink-900 bg-mint-50 px-4 py-2.5">
          <GitMerge className="h-3.5 w-3.5 shrink-0 text-mint-700" />
          <p className="font-mono text-[10.5px] font-medium uppercase tracking-wider text-mint-700">
            el merge vuelve al tablero y reescribe la documentación
          </p>
        </div>
      </div>
    </div>
  )
}
