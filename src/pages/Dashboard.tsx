import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Bot, GitPullRequest, Play, Plus, Plug, Unplug, Users, Zap } from 'lucide-react'
import { AppShell } from '@/components/app/AppShell'
import { NewProjectModal } from '@/components/app/NewProjectModal'
import { Button } from '@/components/ui/Button'
import { Avatar } from '@/components/ui/Avatar'
import { Stamp } from '@/components/ui/Bits'
import { GitHubLogo, SupabaseLogo } from '@/components/brand/Logos'
import { useAppStore } from '@/store/AppStore'
import { getTokens } from '@/lib/api'
import { cn } from '@/lib/cn'

export default function Dashboard() {
  const { projects, collaborators, user } = useAppStore()
  const [modalOpen, setModalOpen] = useState(false)
  const navigate = useNavigate()

  const totalTasks = projects.reduce((s, p) => s + p.tasks.length, 0)
  const doneTasks = projects.reduce(
    (s, p) => s + p.tasks.filter((t) => t.status === 'done').length,
    0,
  )
  const connected = projects.filter((p) => p.repo).length

  return (
    <AppShell onNewProject={() => setModalOpen(true)}>
      <div className="mx-auto w-full max-w-7xl px-5 py-9 sm:px-8 sm:py-12">
        {/* Encabezado */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="label-mono text-ink-400">
              {user ? `sesión · ${user.name.split(' ')[0]}` : 'bienvenido'}
            </p>
            <h1 className="mt-2 font-display text-[38px] leading-none tracking-tightest text-ink-900 sm:text-[46px]">
              Centro de Control
            </h1>
          </div>
          <Button onClick={() => setModalOpen(true)}>
            <Plus className="h-4 w-4" />
            Nuevo proyecto
          </Button>
        </div>

        {/* Layout principal: 2 columnas */}
        <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_380px]">

          {/* Columna izquierda: Agentes + Chat */}
          <div>
            <AgentsPanel />
          </div>

          {/* Columna derecha: Integraciones + Resumen */}
          <div className="space-y-6">
            {/* Integraciones */}
            <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
              <div className="flex items-center gap-2 mb-4">
                <Plug className="h-4 w-4 text-violet-600" />
                <h3 className="text-[15px] font-bold text-ink-900">Integraciones</h3>
              </div>
              <div className="space-y-2.5">
                {[
                  { name: 'GitHub', icon: '🐙', url: 'https://hackaton-codigo-facilito-agentes.onrender.com/auth/oauth/github/login', desc: 'Repos, PRs, issues' },
                  { name: 'Jira', icon: '📋', url: 'https://hackaton-codigo-facilito-agentes.onrender.com/oauth/jira/authorize?token=demo', desc: 'Issues, sprints' },
                  { name: 'Vercel', icon: '▲', url: 'https://hackaton-codigo-facilito-agentes.onrender.com/oauth/vercel/authorize?token=demo', desc: 'Deploys, logs' },
                  { name: 'Slack', icon: '💬', url: 'https://hackaton-codigo-facilito-agentes.onrender.com/oauth/slack/authorize?token=demo', desc: 'Alertas' },
                ].map((integration) => (
                  <a
                    key={integration.name}
                    href={integration.url}
                    className="flex items-center gap-3 rounded-lg border-2 border-ink-200 p-2.5 transition hover:border-violet-600 hover:bg-violet-50"
                  >
                    <span className="text-lg">{integration.icon}</span>
                    <div className="flex-1 min-w-0">
                      <span className="text-[12px] font-bold text-ink-900">{integration.name}</span>
                      <span className="ml-1.5 text-[10px] text-ink-400">{integration.desc}</span>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 text-ink-300" />
                  </a>
                ))}
              </div>
            </div>

            {/* Resumen */}
            <div className="rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard">
              <p className="label-mono text-ink-400 mb-3">resumen</p>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-ink-600">Proyectos</span>
                  <span className="font-display text-[20px] text-ink-900">{projects.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-ink-600">Tareas cerradas</span>
                  <span className="font-display text-[20px] text-ink-900">{doneTasks}/{totalTasks}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-ink-600">Repos conectados</span>
                  <span className="font-display text-[20px] text-ink-900">{connected}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[12px] text-ink-600">Colaboradores</span>
                  <span className="font-display text-[20px] text-ink-900">{collaborators.length}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Proyectos — debajo */}
        <div className="mt-10">
          <h2 className="font-display text-[24px] tracking-tightest text-ink-900 mb-5">Proyectos</h2>
          <div className="grid gap-5 lg:grid-cols-2">
          {projects.map((p, i) => {
            const done = p.tasks.filter((t) => t.status === 'done').length
            const pct = p.tasks.length ? Math.round((done / p.tasks.length) * 100) : 0
            const people = collaborators.filter((c) => p.collaboratorIds.includes(c.id))
            const budgetPct = p.budget.allocated
              ? Math.round((p.budget.spent / p.budget.allocated) * 100)
              : 0

            return (
              <motion.div
                key={p.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 + i * 0.07 }}
              >
                <Link
                  to={`/app/proyecto/${p.id}`}
                  className="group flex h-full flex-col rounded-xl border-2 border-ink-900 bg-paper shadow-hard transition-transform hover:-translate-y-1"
                >
                  {/* franja de color del proyecto */}
                  <div
                    className="h-1.5 rounded-t-[10px]"
                    style={{ background: `hsl(${p.hue} 62% 60%)` }}
                  />

                  <div className="flex flex-1 flex-col p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="truncate text-[18px] font-extrabold tracking-tight text-ink-900">
                          {p.name}
                        </h2>
                        <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-ink-600">
                          {p.description}
                        </p>
                      </div>
                      <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-ink-300 transition-all group-hover:translate-x-1 group-hover:text-violet-600" />
                    </div>

                    {/* chips de conexión */}
                    <div className="mt-4 flex flex-wrap items-center gap-1.5">
                      {p.repo ? (
                        <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                          <GitHubLogo className="h-3 w-3" />
                          {p.repo.fullName}
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 rounded border-2 border-clay-500 bg-clay-100 px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-clay-700">
                          <Unplug className="h-3 w-3" />
                          sin repo
                        </span>
                      )}
                      {p.database && (
                        <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                          <SupabaseLogo className="h-3 w-3" />
                          {p.database.tables} tablas
                        </span>
                      )}
                      {p.repo && (
                        <span className="inline-flex items-center gap-1.5 rounded border-2 border-ink-900 bg-paper px-2 py-0.5 font-mono text-[10px] font-medium text-ink-800">
                          <GitPullRequest className="h-3 w-3" />
                          {p.repo.stats.openPRs} PRs
                        </span>
                      )}
                    </div>

                    {/* progreso segmentado */}
                    <div className="mt-5 flex-1 space-y-4">
                      <div>
                        <div className="mb-1.5 flex items-center justify-between">
                          <span className="label-mono text-ink-400">avance verificado</span>
                          <span className="font-mono text-[11px] font-bold text-ink-900">
                            {done}/{p.tasks.length} · {pct}%
                          </span>
                        </div>
                        <div className="flex h-2.5 gap-[2px] rounded border-2 border-ink-900 bg-paper p-[2px]">
                          {Array.from({ length: 16 }, (_, k) => (
                            <motion.span
                              key={k}
                              className={cn(
                                'flex-1',
                                k < Math.round((pct / 100) * 16) ? 'bg-mint-500' : 'bg-ink-100',
                              )}
                              initial={{ scaleY: 0 }}
                              animate={{ scaleY: 1 }}
                              transition={{ delay: 0.3 + k * 0.02 }}
                            />
                          ))}
                        </div>
                      </div>

                      {p.budget.allocated > 0 && (
                        <div>
                          <div className="mb-1.5 flex items-center justify-between">
                            <span className="label-mono text-ink-400">presupuesto</span>
                            <span
                              className={cn(
                                'font-mono text-[11px] font-bold tabular-nums',
                                budgetPct > 85 ? 'text-clay-700' : 'text-ink-900',
                              )}
                            >
                              ${p.budget.spent.toLocaleString('en-US')} / $
                              {p.budget.allocated.toLocaleString('en-US')}
                            </span>
                          </div>
                          <div className="flex h-2.5 gap-[2px] rounded border-2 border-ink-900 bg-paper p-[2px]">
                            {Array.from({ length: 16 }, (_, k) => (
                              <motion.span
                                key={k}
                                className={cn(
                                  'flex-1',
                                  k < Math.round((budgetPct / 100) * 16)
                                    ? budgetPct > 85
                                      ? 'bg-clay-500'
                                      : 'bg-violet-600'
                                    : 'bg-ink-100',
                                )}
                                initial={{ scaleY: 0 }}
                                animate={{ scaleY: 1 }}
                                transition={{ delay: 0.4 + k * 0.02 }}
                              />
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* pie */}
                    <div className="mt-5 flex items-center justify-between border-t-2 border-dashed border-ink-200 pt-4">
                      <div className="flex items-center gap-2">
                        <div className="flex -space-x-1.5">
                          {people.slice(0, 4).map((c) => (
                            <span key={c.id} className="rounded-full border-2 border-ink-900">
                              <Avatar name={c.name} hue={c.avatarHue} size={24} ring={false} />
                            </span>
                          ))}
                        </div>
                        <span className="flex items-center gap-1 font-mono text-[10.5px] text-ink-400">
                          <Users className="h-3 w-3" />
                          {people.length}
                        </span>
                      </div>
                      {p.repo && (
                        <span className="font-mono text-[9.5px] uppercase tracking-wider text-ink-400">
                          sync {p.repo.lastSync}
                        </span>
                      )}
                    </div>
                  </div>
                </Link>
              </motion.div>
            )
          })}

          {/* Crear */}
          <motion.button
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + projects.length * 0.07 }}
            onClick={() => setModalOpen(true)}
            className="group flex min-h-[240px] flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-ink-300 bg-paper/60 p-6 transition-colors hover:border-violet-600 hover:bg-violet-50"
          >
            <span className="grid h-12 w-12 place-items-center rounded-lg border-2 border-ink-900 bg-paper transition-all group-hover:-rotate-12 group-hover:bg-violet-600">
              <Plus className="h-5 w-5 text-ink-900 transition-colors group-hover:text-white" />
            </span>
            <span className="text-center">
              <span className="block text-[14.5px] font-bold text-ink-900">Nuevo proyecto</span>
              <span className="mt-0.5 block font-mono text-[10.5px] uppercase tracking-wider text-ink-400">
                tablero + repo
              </span>
            </span>
          </motion.button>
        </div>
        </div>

        {user?.isDemo && (
          <div className="mt-10 flex justify-center">
            <Stamp tone="violet">datos de demostración</Stamp>
          </div>
        )}
      </div>

      <NewProjectModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={(id) => {
          setModalOpen(false)
          navigate(`/app/proyecto/${id}`)
        }}
      />
    </AppShell>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════ */

interface AgentResult {
  risk_score: number
  severity: string
  is_partial: boolean
  financial_impact: number
  outcomes: Array<{
    agent: string
    score: number
    signals: Array<{ code: string; message: string; weight: number }>
  }>
  primary_reason: string | null
}

function AgentsPanel() {
  const [result, setResult] = useState<AgentResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)

  const agents = [
    {
      name: 'commitment', label: 'Commitment Agent', icon: '📅',
      desc: 'Analiza vencimientos y compromisos',
      howItWorks: 'Evalúa la fecha de vencimiento del compromiso contra la fecha actual. Detecta issues vencidos, próximos a vencer, sin fecha asignada o reabiertos.',
      signals: ['overdue — Compromiso vencido', 'due_soon — Vence en menos de 3 días', 'no_due_date — Sin fecha de entrega', 'reopened — Fue cerrado y reabierto'],
    },
    {
      name: 'technical', label: 'Technical Agent', icon: '⚙️',
      desc: 'Detecta bloqueos y estancamiento',
      howItWorks: 'Analiza el flujo de trabajo técnico: transiciones de estado, asignaciones, actividad reciente. Identifica patrones de riesgo como bloqueos, falta de responsable o estancamiento.',
      signals: ['blocked — Issue marcado como bloqueado', 'unassigned — Sin responsable', 'stale — Sin actividad en X días', 'reassignment_churn — Múltiples reasignaciones'],
    },
    {
      name: 'financial', label: 'Financial Agent', icon: '💰',
      desc: 'Calcula impacto económico',
      howItWorks: 'Toma las horas estimadas del compromiso y el costo/hora del proyecto para calcular el impacto económico si el compromiso falla. Cuantifica el riesgo en USD.',
      signals: ['hours_at_risk — Horas que podrían perderse', 'cost_impact — Costo = horas × tarifa', 'budget_exposure — % del presupuesto en peligro'],
    },
    {
      name: 'risk', label: 'Risk Agent', icon: '🎯',
      desc: 'Compone riesgo global ponderado',
      howItWorks: 'Recibe las salidas de los demás agentes y las combina con pesos declarados. Clasifica el resultado en severidad (low/medium/high/critical) e identifica la señal dominante.',
      signals: ['weighted_score — Score ponderado 0-100', 'severity — low (<40) / medium (40-59) / high (60-79) / critical (80+)', 'dominant_signal — Señal de mayor peso'],
    },
    {
      name: 'orchestrator', label: 'Orchestrator', icon: '🤖',
      desc: 'Ejecuta pipeline completo',
      howItWorks: 'Ejecuta CommitmentAgent, TechnicalAgent y FinancialAgent en secuencia. Si uno falla, continúa con los demás y marca el análisis como parcial (is_partial=true). Luego invoca al RiskAgent para componer el resultado final.',
      signals: ['parallel_execution — Cada agente es independiente', 'fault_tolerance — Fallos aislados', 'result_composition — Agrega en AnalysisResult'],
    },
  ]

  async function runAnalysis() {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const tokens = getTokens()
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (tokens?.access_token) {
        headers['Authorization'] = `Bearer ${tokens.access_token}`
      }
      const res = await fetch('https://hackaton-codigo-facilito-agentes.onrender.com/agents/analyze', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          project_key: 'DATGENT',
          issue_key: 'DATGENT-42',
          title: 'Implementar sistema de multi-agentes',
          due_date: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
          estimated_hours: 40,
          hourly_cost: 75,
        }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || res.statusText)
      }
      const data = await res.json()
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error ejecutando agentes')
    } finally {
      setLoading(false)
    }
  }

  const severityColor: Record<string, string> = {
    low: 'bg-mint-100 text-mint-700 border-mint-300',
    medium: 'bg-clay-100 text-clay-700 border-clay-300',
    high: 'bg-orange-100 text-orange-700 border-orange-300',
    critical: 'bg-rose-100 text-rose-700 border-rose-300',
  }

  return (
    <div className="mt-12">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-violet-600" />
          <h2 className="font-display text-[24px] tracking-tightest text-ink-900">Agentes IA</h2>
        </div>
        <Button onClick={runAnalysis} loading={loading} size="sm">
          <Play className="h-3.5 w-3.5" />
          Ejecutar análisis
        </Button>
      </div>
      <p className="mt-1 text-[13px] text-ink-500">
        Pipeline de agentes especializados para detección de riesgos. Ejecutá manualmente para ver el resultado.
      </p>

      {/* Grid de agentes */}
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {agents.map((agent, i) => (
          <motion.button
            key={agent.name}
            onClick={() => setSelectedAgent(selectedAgent === agent.name ? null : agent.name)}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.04 }}
            className={cn(
              'rounded-xl border-2 bg-paper p-3 shadow-hard-sm text-left transition-all',
              selectedAgent === agent.name
                ? 'border-violet-600 ring-2 ring-violet-200'
                : 'border-ink-900 hover:-translate-y-0.5'
            )}
          >
            <span className="text-lg">{agent.icon}</span>
            <h3 className="mt-1 text-[12px] font-bold text-ink-900">{agent.label}</h3>
            <p className="text-[10px] leading-tight text-ink-500">{agent.desc}</p>
            {result && (
              <div className="mt-2 rounded bg-ink-50 px-1.5 py-1">
                <span className="font-mono text-[10px] font-bold text-violet-700">
                  score: {result.outcomes.find(o => o.agent === agent.name)?.score ?? '—'}
                </span>
              </div>
            )}
          </motion.button>
        ))}
      </div>

      {/* Detalle del agente seleccionado */}
      {selectedAgent && (() => {
        const agent = agents.find(a => a.name === selectedAgent)!
        return (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-4 overflow-hidden rounded-xl border-2 border-violet-600 bg-violet-50 p-5"
          >
            <div className="flex items-center gap-2">
              <span className="text-xl">{agent.icon}</span>
              <h3 className="text-[16px] font-bold text-ink-900">{agent.label}</h3>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-700">{agent.howItWorks}</p>
            <div className="mt-3">
              <p className="label-mono text-violet-700 mb-1.5">señales que emite:</p>
              <ul className="space-y-1">
                {agent.signals.map((signal, si) => (
                  <li key={si} className="flex items-center gap-2 text-[12px] text-ink-700">
                    <Zap className="h-3 w-3 shrink-0 text-violet-500" />
                    <span className="font-mono">{signal}</span>
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        )
      })()}

      {/* Resultado del análisis */}
      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-4 rounded-xl border-2 border-rose-300 bg-rose-50 p-4"
        >
          <p className="text-[13px] font-medium text-rose-700">{error}</p>
        </motion.div>
      )}

      {result && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-5 rounded-xl border-2 border-ink-900 bg-paper p-5 shadow-hard"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-[16px] font-bold text-ink-900">Resultado del Análisis</h3>
            <span className={cn(
              'rounded-full border px-3 py-1 font-mono text-[11px] font-bold uppercase',
              severityColor[result.severity] || 'bg-ink-100 text-ink-600'
            )}>
              {result.severity} · {result.risk_score}/100
            </span>
          </div>

          {result.is_partial && (
            <p className="mt-2 text-[11px] font-medium text-clay-600">
              ⚠️ Análisis parcial — algún agente no pudo ejecutarse
            </p>
          )}

          {result.financial_impact > 0 && (
            <p className="mt-2 text-[13px] text-ink-700">
              💰 Impacto económico estimado: <span className="font-bold">${result.financial_impact.toLocaleString()}</span>
            </p>
          )}

          {result.primary_reason && (
            <p className="mt-1 text-[13px] text-ink-700">
              🎯 Señal dominante: <span className="font-mono font-bold text-violet-700">{result.primary_reason}</span>
            </p>
          )}

          {/* Señales por agente */}
          <div className="mt-4 space-y-3">
            {result.outcomes.map((outcome) => (
              <div key={outcome.agent} className="rounded-lg border border-ink-200 p-3">
                <div className="flex items-center justify-between">
                  <span className="text-[12px] font-bold text-ink-900 capitalize">{outcome.agent}</span>
                  <span className="font-mono text-[11px] font-bold text-violet-700">{outcome.score}/100</span>
                </div>
                {outcome.signals.length > 0 && (
                  <ul className="mt-1.5 space-y-0.5">
                    {outcome.signals.map((signal, si) => (
                      <li key={si} className="flex items-center gap-2 text-[11px] text-ink-600">
                        <Zap className="h-3 w-3 text-clay-500" />
                        <span className="font-mono text-[9px] text-ink-400">[{signal.code}]</span>
                        {signal.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {/* ═══ Chat con Agentes ═══ */}
      <AgentChat />
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════════ */

interface ChatMessage {
  role: 'user' | 'agent'
  content: string
  agent?: string
}

function AgentChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'agent', content: 'Hola! Soy el Orchestrator de Datgent. Preguntame sobre riesgos, compromisos o impacto financiero de tus proyectos.', agent: 'orchestrator' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)

    try {
      // Ejecutar análisis con el texto como título del issue
      const tokens = getTokens()
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (tokens?.access_token) headers['Authorization'] = `Bearer ${tokens.access_token}`

      const res = await fetch('https://hackaton-codigo-facilito-agentes.onrender.com/agents/analyze', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          project_key: 'CHAT',
          issue_key: 'CHAT-' + Date.now(),
          title: userMsg,
          due_date: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
          estimated_hours: 20,
          hourly_cost: 60,
        }),
      })

      if (!res.ok) throw new Error('Error del servidor')
      const data = await res.json()

      // Formatear respuesta de los agentes
      const signals = data.outcomes
        .flatMap((o: { agent: string; signals: Array<{ message: string }> }) =>
          o.signals.map((s: { message: string }) => `• **${o.agent}**: ${s.message}`)
        )
        .join('\n')

      const response = [
        `📊 **Análisis de riesgo:** ${data.risk_score}/100 (${data.severity})`,
        data.financial_impact > 0 ? `💰 **Impacto:** $${data.financial_impact.toLocaleString()}` : '',
        data.primary_reason ? `🎯 **Razón principal:** ${data.primary_reason}` : '',
        signals ? `\n**Señales detectadas:**\n${signals}` : 'No se detectaron señales de riesgo.',
      ].filter(Boolean).join('\n')

      setMessages(prev => [...prev, { role: 'agent', content: response, agent: 'orchestrator' }])
    } catch {
      setMessages(prev => [...prev, {
        role: 'agent',
        content: 'Servidor cargando... Intentá de nuevo en unos segundos.',
        agent: 'orchestrator',
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mt-8 rounded-xl border-2 border-ink-900 bg-paper shadow-hard overflow-hidden">
      <div className="flex items-center gap-2 border-b-2 border-ink-200 bg-violet-50 px-4 py-3">
        <Bot className="h-4 w-4 text-violet-600" />
        <span className="text-[13px] font-bold text-ink-900">Chat con Agentes</span>
        <span className="ml-auto rounded-full bg-mint-100 px-2 py-0.5 font-mono text-[9px] font-bold text-mint-700 border border-mint-300">
          en vivo
        </span>
      </div>

      {/* Messages */}
      <div className="h-[300px] overflow-y-auto p-4 space-y-3">
        {messages.map((msg, i) => (
          <div key={i} className={cn('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            <div className={cn(
              'max-w-[80%] rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed',
              msg.role === 'user'
                ? 'bg-violet-600 text-white'
                : 'bg-ink-100 text-ink-800'
            )}>
              {msg.role === 'agent' && (
                <span className="mb-1 block font-mono text-[9px] font-bold uppercase text-violet-600">
                  🤖 {msg.agent}
                </span>
              )}
              <span className="whitespace-pre-wrap">{msg.content}</span>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-xl bg-ink-100 px-3.5 py-2.5">
              <span className="flex items-center gap-1.5 text-[12px] text-ink-500">
                <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-violet-400" />
                Analizando...
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="flex items-center gap-2 border-t-2 border-ink-200 p-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describí un compromiso o preguntá sobre riesgos..."
          className="flex-1 rounded-lg border-2 border-ink-200 bg-paper px-3 py-2 text-[13px] text-ink-900 placeholder:text-ink-400 focus:border-violet-600 focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="grid h-9 w-9 place-items-center rounded-lg border-2 border-ink-900 bg-violet-600 text-white transition hover:bg-violet-700 disabled:opacity-40"
        >
          <ArrowRight className="h-4 w-4" />
        </button>
      </form>
    </div>
  )
}
