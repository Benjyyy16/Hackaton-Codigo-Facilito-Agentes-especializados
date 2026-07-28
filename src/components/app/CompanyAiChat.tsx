import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, Send, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import { OrquestaMark } from '@/components/brand/Logos'
import { sendAgentMessage, type ChatMessage } from '@/lib/chatApi'
import { errorMessage } from '@/lib/http'
import { cn } from '@/lib/cn'

const starter: ChatMessage[] = [
  {
    role: 'assistant',
    content:
      'Soy Datgent Cerebro. Envíame mensajes de tu empresa y respondo con contexto, riesgos y próximos pasos.',
  },
]

const agentPrompts = [
  ['Estratega', 'prioriza el siguiente movimiento para la empresa'],
  ['Auditor', 'detecta riesgos, bloqueos y deuda'],
  ['Builder', 'propón acciones ejecutables para el equipo'],
  ['Reviewer', 'revisa si algo no debería avanzar sin aprobación'],
] as const

export function CompanyAiChat({
  onCreateExample,
  compact = false,
  context = '',
}: {
  onCreateExample: () => void
  compact?: boolean
  context?: string
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(starter)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const [runningAgent, setRunningAgent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const send = useCallback(async (raw?: string, agentName?: string) => {
    const text = (raw ?? draft).trim()
    if (!text || loading) return
    const next = [...messages, { role: 'user' as const, content: text }]
    setMessages(next)
    setDraft('')
    setError(null)
    setLoading(true)
    setRunningAgent(agentName ?? 'Datgent Cerebro')
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const prompt = [
        'Actúa como Datgent Cerebro para empresas.',
        'Responde el mensaje recibido de forma útil, concreta y accionable.',
        'Usa agentes internos cuando aplique: Estratega, Auditor, Builder, Reviewer.',
        'Nunca inventes datos; si falta contexto, pide el dato mínimo.',
        context ? `Contexto del dashboard:\n${context}` : '',
        `Mensaje recibido:\n${text}`,
      ].filter(Boolean).join('\n\n')
      const res = await sendAgentMessage(prompt, messages, controller.signal)
      setMessages([...next, { role: 'assistant', content: res.response }])
    } catch (err) {
      setError(errorMessage(err, 'No pude responder ahora.'))
    } finally {
      setLoading(false)
      setRunningAgent(null)
    }
  }, [context, draft, loading, messages])

  return (
    <section className="overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-ink-100 bg-violet-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-lg border-2 border-ink-900 bg-violet-600 text-white">
            <OrquestaMark className="h-7 w-7" />
          </span>
          <div>
            <p className="text-[15px] font-extrabold text-ink-900">Datgent IA para empresas</p>
            <p className="font-mono text-[10px] uppercase tracking-wider text-ink-400">
              responde mensajes · usa agentes · contexto vivo
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {agentPrompts.map(([agent, prompt]) => (
            <button
              key={agent}
              onClick={() => void send(`${agent}: ${prompt}`, agent)}
              className="rounded border-2 border-ink-900 bg-paper px-2 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-ink-700 transition-colors hover:bg-violet-600 hover:text-white"
            >
              {agent}
            </button>
          ))}
        </div>
      </div>

      <div className={compact ? '' : 'grid gap-0 lg:grid-cols-[1fr_300px]'}>
        <div className={compact ? 'p-3 sm:p-4' : 'p-4'}>
          {runningAgent && (
            <div className="mb-3 overflow-hidden rounded-xl border-2 border-ink-900 bg-[#090711] shadow-hard">
              <div className="flex h-8 items-center gap-2 border-b border-white/10 px-3">
                <span className="h-2 w-2 rounded-full bg-ink-500" />
                <span className="h-2 w-2 rounded-full bg-ink-500" />
                <span className="h-2 w-2 rounded-full bg-mint-500" />
                <span className="ml-2 font-mono text-[9px] uppercase tracking-[0.2em] text-white/45">
                  datgent · ejecución
                </span>
              </div>
              <div className="flex items-center gap-2 px-4 py-3 font-mono text-[12px] text-mint-300">
                <span className="text-white/35">$</span>
                <span>{runningAgent.toLowerCase()} procesando mensaje...</span>
                <span className="h-5 w-2 animate-pulse bg-violet-500" />
              </div>
            </div>
          )}

          <div className={compact ? 'max-h-[170px] space-y-2 overflow-y-auto rounded-lg border-2 border-ink-100 bg-paper-100 p-2' : 'max-h-[280px] space-y-2 overflow-y-auto rounded-lg border-2 border-ink-100 bg-paper-100 p-3'}>
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
                <p
                  className={cn(
                    'inline-block max-w-[88%] rounded-lg border-2 px-3 py-2 leading-relaxed',
                    compact ? 'text-[12px]' : 'text-[13px]',
                    m.role === 'user'
                      ? 'border-violet-600 bg-violet-600 text-white'
                      : 'border-ink-900 bg-paper text-ink-800',
                  )}
                >
                  {m.content}
                </p>
              </div>
            ))}
            {loading && (
              <p className="inline-flex items-center gap-2 rounded-lg border-2 border-ink-900 bg-paper px-3 py-2 text-[13px] text-ink-600">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                consultando agentes…
              </p>
            )}
          </div>

          {error && <p className="mt-2 text-[12px] font-medium text-clay-700">{error}</p>}

          <div className="mt-3 flex gap-2">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void send()
              }}
              placeholder="Escribe un mensaje para Datgent..."
              className="min-w-0 flex-1 rounded-lg border-2 border-ink-900 bg-paper px-3 py-2 text-[13px] outline-none focus:ring-2 focus:ring-violet-300"
            />
            <button
              onClick={() => void send()}
              disabled={loading || !draft.trim()}
              className="grid h-10 w-10 place-items-center rounded-lg border-2 border-ink-900 bg-violet-600 text-white shadow-hard-sm disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>

        {!compact && <aside className="border-t-2 border-ink-900 bg-ink-900 p-4 text-white lg:border-l-2 lg:border-t-0">
          <Sparkles className="h-5 w-5 text-violet-600" />
          <p className="mt-3 text-[18px] font-extrabold leading-tight">
            ¿Quieres crear un repo de ejemplo para probar?
          </p>
          <p className="mt-2 text-[12.5px] leading-relaxed text-white/70">
            El chat responde mensajes de empresa y puede activar agentes sobre tus tableros.
          </p>
          <button
            onClick={onCreateExample}
            className="mt-4 w-full rounded-lg border-2 border-ink-900 bg-mint-500 px-3 py-2 text-[13px] font-extrabold text-ink-900 shadow-hard-sm transition-transform hover:-translate-y-0.5"
          >
            Crear repo de ejemplo
          </button>
        </aside>}
      </div>
    </section>
  )
}

export function AnalysisTerminal({ active }: { active: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="overflow-hidden rounded-xl border-2 border-ink-900 bg-[#090711] shadow-hard"
    >
      <div className="flex h-9 items-center gap-2 border-b border-white/10 px-3">
        <span className="h-2.5 w-2.5 rounded-full bg-ink-500" />
        <span className="h-2.5 w-2.5 rounded-full bg-ink-500" />
        <span className="h-2.5 w-2.5 rounded-full bg-mint-500" />
        <span className="ml-3 font-mono text-[10px] uppercase tracking-[0.2em] text-white/45">
          datgent · bitácora
        </span>
      </div>
      <div className="flex items-center gap-3 px-5 py-5 font-mono text-[15px] text-mint-300 sm:text-[17px]">
        <span className="text-white/35">$</span>
        <span>{active ? 'analizando 1284 commits en main…' : 'listo para analizar main'}</span>
        {active && <span className="h-7 w-2 animate-pulse bg-violet-500" />}
      </div>
    </motion.div>
  )
}
