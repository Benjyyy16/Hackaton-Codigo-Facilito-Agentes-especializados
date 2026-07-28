import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot, Loader2, Send, Sparkles } from 'lucide-react'
import { motion } from 'framer-motion'
import { Button } from '@/components/ui/Button'
import { sendAgentMessage, type ChatMessage } from '@/lib/chatApi'
import { errorMessage } from '@/lib/http'

const starter: ChatMessage[] = [
  {
    role: 'assistant',
    content:
      'Soy Datgent Cerebro. Puedo revisar riesgos, priorizar backlog y proponer acciones con tus agentes.',
  },
]

export function CompanyAiChat({
  onCreateExample,
}: {
  onCreateExample: () => void
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(starter)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => () => abortRef.current?.abort(), [])

  const send = useCallback(async () => {
    const text = draft.trim()
    if (!text || loading) return
    const next = [...messages, { role: 'user' as const, content: text }]
    setMessages(next)
    setDraft('')
    setError(null)
    setLoading(true)
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const res = await sendAgentMessage(text, messages, controller.signal)
      setMessages([...next, { role: 'assistant', content: res.response }])
    } catch (err) {
      setError(errorMessage(err, 'No pude responder ahora.'))
    } finally {
      setLoading(false)
    }
  }, [draft, loading, messages])

  return (
    <section className="overflow-hidden rounded-xl border-2 border-ink-900 bg-paper shadow-hard">
      <div className="grid gap-0 lg:grid-cols-[1fr_320px]">
        <div className="p-4 sm:p-5">
          <div className="flex items-center gap-2">
            <span className="grid h-9 w-9 place-items-center rounded-lg border-2 border-ink-900 bg-violet-600 text-white">
              <Bot className="h-4 w-4" />
            </span>
            <div>
              <p className="label-mono text-ink-400">chat ia para empresas</p>
              <h2 className="text-[20px] font-extrabold text-ink-900">Habla con Datgent</h2>
            </div>
          </div>

          <div className="mt-4 max-h-[360px] space-y-3 overflow-y-auto rounded-lg border-2 border-ink-100 bg-paper-100 p-3">
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
                <p
                  className={`inline-block max-w-[88%] rounded-lg border-2 px-3 py-2 text-[13px] leading-relaxed ${
                    m.role === 'user'
                      ? 'border-violet-600 bg-violet-600 text-white'
                      : 'border-ink-900 bg-paper text-ink-800'
                  }`}
                >
                  {m.content}
                </p>
              </div>
            ))}
            {loading && (
              <p className="inline-flex items-center gap-2 rounded-lg border-2 border-ink-900 bg-paper px-3 py-2 text-[13px] text-ink-600">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                pensando con agentes…
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
              placeholder="Ej: ¿qué riesgo tiene lanzar el viernes?"
              className="min-w-0 flex-1 rounded-lg border-2 border-ink-900 bg-paper px-3 py-2 text-[13px] outline-none focus:ring-2 focus:ring-violet-300"
            />
            <Button onClick={() => void send()} disabled={loading || !draft.trim()}>
              <Send className="h-4 w-4" />
              Enviar
            </Button>
          </div>
        </div>

        <aside className="border-t-2 border-ink-900 bg-violet-50 p-4 lg:border-l-2 lg:border-t-0">
          <Sparkles className="h-5 w-5 text-violet-600" />
          <p className="mt-3 text-[18px] font-extrabold leading-tight text-ink-900">
            ¿Quieres crear un repo de ejemplo para probar?
          </p>
          <p className="mt-2 text-[12.5px] leading-relaxed text-ink-600">
            Datgent puede analizar una base mínima, levantar agentes y mostrar decisiones.
          </p>
          <button
            onClick={onCreateExample}
            className="mt-4 w-full rounded-lg border-2 border-ink-900 bg-mint-500 px-3 py-2 text-[13px] font-extrabold text-ink-900 shadow-hard-sm transition-transform hover:-translate-y-0.5"
          >
            Crear repo de ejemplo
          </button>
        </aside>
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
