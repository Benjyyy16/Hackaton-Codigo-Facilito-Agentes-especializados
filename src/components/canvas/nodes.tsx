import { Handle, Position, type NodeProps } from 'reactflow'
import { motion } from 'framer-motion'
import {
  Bot,
  Check,
  CircleDollarSign,
  FileText,
  GitBranch,
  GitPullRequest,
  RefreshCw,
  User as UserIcon,
} from 'lucide-react'
import { GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'
import { cn } from '@/lib/cn'
import type { TaskStatus } from '@/store/types'

/** Envoltura común: borde duro + sombra desplazada, sobre papel. */
const shell = 'rounded-lg border-2 border-ink-900 bg-paper shadow-hard-sm'

/* ================= Nodo: repositorio GitHub ================= */

export type RepoNodeData = {
  fullName: string
  branch: string
  commits: number
  openPRs: number
  mergedPRs: number
  coverage: number
  lastSync: string
}

export function RepoNode({ data }: NodeProps<RepoNodeData>) {
  return (
    <div className={cn(shell, 'w-[236px] overflow-hidden')}>
      <div className="flex items-center gap-2 border-b-2 border-ink-900 bg-ink-900 px-3 py-2">
        <GitHubLogo className="h-4 w-4 shrink-0 text-white" />
        <span className="flex-1 truncate font-mono text-[11px] font-medium text-white">
          {data.fullName}
        </span>
        <motion.span
          className="h-2 w-2 shrink-0 rounded-full bg-mint-500"
          animate={{ opacity: [1, 0.25, 1] }}
          transition={{ duration: 1.8, repeat: Infinity }}
        />
      </div>
      <div className="p-3">
        <div className="grid grid-cols-2 gap-1.5">
          {[
            { l: 'commits', v: data.commits.toLocaleString('en-US') },
            { l: 'prs abiertos', v: String(data.openPRs) },
            { l: 'prs merged', v: String(data.mergedPRs) },
            { l: 'cobertura', v: `${data.coverage}%` },
          ].map((s) => (
            <div key={s.l} className="rounded border border-ink-200 bg-paper-100 px-2 py-1">
              <p className="font-mono text-[8.5px] uppercase tracking-wider text-ink-400">{s.l}</p>
              <p className="text-[13px] font-bold tabular-nums text-ink-900">{s.v}</p>
            </div>
          ))}
        </div>
        <p className="mt-2 flex items-center gap-1.5 font-mono text-[9.5px] text-ink-400">
          <GitBranch className="h-2.5 w-2.5" />
          {data.branch} · sync {data.lastSync}
        </p>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

/* ================= Nodo: base Supabase ================= */

export type DbNodeData = {
  projectRef: string
  region: string
  tables: number
  migrations: number
  rlsEnabled: boolean
}

export function DbNode({ data }: NodeProps<DbNodeData>) {
  return (
    <div className={cn(shell, 'w-[214px] overflow-hidden')}>
      <div className="flex items-center gap-2 border-b-2 border-ink-900 bg-mint-100 px-3 py-2">
        <SupabaseLogo className="h-4 w-4 shrink-0" />
        <span className="flex-1 text-[12px] font-bold text-ink-900">Supabase</span>
      </div>
      <div className="space-y-2 p-3">
        <p className="truncate font-mono text-[9.5px] text-ink-400">{data.projectRef}</p>
        <div className="flex flex-wrap gap-1.5">
          <span className="rounded border border-ink-200 bg-paper-100 px-1.5 py-0.5 font-mono text-[9.5px] font-medium text-ink-700">
            {data.tables} tablas
          </span>
          <span className="rounded border border-ink-200 bg-paper-100 px-1.5 py-0.5 font-mono text-[9.5px] font-medium text-ink-700">
            {data.migrations} migr.
          </span>
          {data.rlsEnabled && (
            <span className="inline-flex items-center gap-1 rounded border border-mint-600 bg-mint-100 px-1.5 py-0.5 font-mono text-[9.5px] font-bold text-mint-700">
              <Check className="h-2.5 w-2.5" />
              RLS
            </span>
          )}
        </div>
        <p className="font-mono text-[9px] uppercase tracking-wider text-ink-300">{data.region}</p>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

/* ================= Nodo: agente ================= */

export type AgentNodeData = {
  name: string
  role: string
  activity: string
  busy: boolean
}

export function AgentNode({ data }: NodeProps<AgentNodeData>) {
  return (
    <div
      className={cn(
        'w-[196px] rounded-lg border-2 border-ink-900 p-3 shadow-hard-sm',
        data.busy ? 'bg-violet-50' : 'bg-paper',
      )}
    >
      <Handle type="target" position={Position.Left} />
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            'relative grid h-8 w-8 shrink-0 place-items-center rounded border-2 border-ink-900',
            data.busy ? 'bg-violet-600 text-white' : 'bg-paper text-violet-600',
          )}
        >
          <Bot className="h-4 w-4" />
          {data.busy && (
            <motion.span
              className="absolute -right-1 -top-1 h-2.5 w-2.5 border-2 border-ink-900 bg-mint-500"
              animate={{ rotate: [0, 180, 360] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
            />
          )}
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-bold text-ink-900">{data.name}</p>
          <p className="truncate font-mono text-[9px] uppercase tracking-wider text-ink-400">
            {data.role}
          </p>
        </div>
      </div>
      <p className="mt-2.5 flex items-start gap-1.5 text-[11px] leading-snug text-ink-600">
        {data.busy && (
          <RefreshCw className="mt-0.5 h-2.5 w-2.5 shrink-0 animate-spin text-violet-600" />
        )}
        {data.activity}
      </p>
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

/* ================= Nodo: tarea ================= */

export type TaskNodeData = {
  title: string
  status: TaskStatus
  owner: string
  bot: boolean
  ref?: string
  autoSynced?: boolean
  points?: number
}

const statusMeta: Record<TaskStatus, { label: string; bg: string; dot: string }> = {
  backlog: { label: 'backlog', bg: 'bg-paper', dot: 'bg-ink-300' },
  progress: { label: 'en curso', bg: 'bg-violet-50', dot: 'bg-violet-500' },
  review: { label: 'revisión', bg: 'bg-clay-100', dot: 'bg-clay-500' },
  done: { label: 'hecho', bg: 'bg-mint-50', dot: 'bg-mint-500' },
}

export function TaskNode({ data }: NodeProps<TaskNodeData>) {
  const m = statusMeta[data.status]
  return (
    <div
      className={cn('w-[212px] rounded-lg border-2 border-ink-900 p-3 shadow-hard-sm', m.bg)}
    >
      <Handle type="target" position={Position.Left} />
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 font-mono text-[9px] font-bold uppercase tracking-wider text-ink-600">
          <span className={cn('h-2 w-2 border border-ink-900', m.dot)} />
          {m.label}
        </span>
        {data.points != null && (
          <span className="rounded border border-ink-200 bg-paper px-1.5 py-0.5 font-mono text-[9px] font-bold text-ink-500">
            {data.points} pts
          </span>
        )}
      </div>

      <p className="mt-2 text-[12.5px] font-semibold leading-snug text-ink-900">{data.title}</p>

      <div className="mt-2.5 flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5 text-[10px] font-medium text-ink-500">
          {data.bot ? (
            <Bot className="h-2.5 w-2.5 shrink-0 text-violet-600" />
          ) : (
            <UserIcon className="h-2.5 w-2.5 shrink-0 text-mint-600" />
          )}
          <span className="truncate">{data.owner}</span>
        </span>
        {data.ref && (
          <span className="inline-flex shrink-0 items-center gap-1 rounded border border-ink-200 bg-paper px-1.5 py-0.5 font-mono text-[8.5px] font-medium text-ink-600">
            {data.ref.startsWith('PR') ? (
              <GitPullRequest className="h-2.5 w-2.5" />
            ) : (
              <GitBranch className="h-2.5 w-2.5" />
            )}
            {data.ref}
          </span>
        )}
      </div>

      {data.autoSynced && (
        <p className="mt-2 flex items-center gap-1 border-t-2 border-dashed border-ink-200 pt-2 font-mono text-[9px] font-bold uppercase tracking-wider text-mint-700">
          <RefreshCw className="h-2.5 w-2.5" />
          movida por el repo
        </p>
      )}
      <Handle type="source" position={Position.Right} />
    </div>
  )
}

/* ================= Nodo: salida / reporte ================= */

export type OutputNodeData = {
  title: string
  kind: 'doc' | 'finance'
  lines: string[]
}

export function OutputNode({ data }: NodeProps<OutputNodeData>) {
  const Icon = data.kind === 'finance' ? CircleDollarSign : FileText
  return (
    <div className={cn(shell, 'w-[222px] overflow-hidden')}>
      <Handle type="target" position={Position.Left} />
      <div className="flex items-center gap-2 border-b-2 border-ink-900 bg-paper-200 px-3 py-2">
        <Icon
          className={cn(
            'h-4 w-4 shrink-0',
            data.kind === 'finance' ? 'text-mint-700' : 'text-violet-600',
          )}
        />
        <span className="flex-1 truncate text-[12px] font-bold text-ink-900">{data.title}</span>
      </div>
      <div className="space-y-1.5 p-3">
        {data.lines.map((l) => (
          <p key={l} className="flex items-start gap-1.5 text-[11px] leading-snug text-ink-600">
            <span className="mt-1 h-[6px] w-[6px] shrink-0 rotate-45 border border-ink-900 bg-violet-300" />
            {l}
          </p>
        ))}
      </div>
    </div>
  )
}

/* ================= Nodo: repo sin conectar ================= */

export function EmptyRepoNode({ data }: NodeProps<{ onConnect?: () => void }>) {
  return (
    <button
      onClick={data.onConnect}
      className="group w-[228px] rounded-lg border-2 border-dashed border-clay-500 bg-clay-100 p-4 text-left transition-colors hover:border-violet-600 hover:bg-violet-50"
    >
      <GitHubLogo className="h-6 w-6 text-ink-700 transition-colors group-hover:text-ink-900" />
      <p className="mt-3 text-[13px] font-bold text-ink-900">Conectá un repositorio</p>
      <p className="mt-1 text-[11px] leading-relaxed text-ink-600">
        Sin repo, el tablero no puede verificar avance.
      </p>
      <Handle type="source" position={Position.Right} />
    </button>
  )
}

export const nodeTypes = {
  repo: RepoNode,
  db: DbNode,
  agent: AgentNode,
  task: TaskNode,
  output: OutputNode,
  emptyRepo: EmptyRepoNode,
}
