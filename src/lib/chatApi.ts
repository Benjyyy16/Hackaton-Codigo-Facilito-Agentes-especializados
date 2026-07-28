import { authHeaders } from '@/lib/authApi'
import { requestJson } from '@/lib/http'

const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface ChatResponse {
  response: string
  agent: string
}

export function sendAgentMessage(
  message: string,
  history: ChatMessage[],
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return requestJson<ChatResponse>(`${BASE}/agents/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ message, history }),
    timeoutMs: 30_000,
    signal,
  })
}
