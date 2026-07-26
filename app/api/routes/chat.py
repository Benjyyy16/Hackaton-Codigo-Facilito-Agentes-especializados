"""Chat endpoint usando OpenAI para los agentes."""

from __future__ import annotations


import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/agents", tags=["agents-chat"])

OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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",
)

SYSTEM_PROMPT = """Eres Datgent Cerebro, el núcleo de inteligencia multiagente de Datgent. Coordinas agentes especializados que detectan riesgos en compromisos de proyectos de software.

Presentate siempre como "Datgent Cerebro". Nunca como "Orchestrator".

Coordinas 5 agentes especializados:
1. **Commitment Agent** — Analiza vencimientos: detecta overdue, due_soon, no_due_date, reopened
2. **Technical Agent** — Detecta bloqueos, estancamiento, sin asignar, reasignaciones
3. **Financial Agent** — Calcula impacto económico: horas × costo/hora
4. **Risk Agent** — Compone score global 0-100 con severidad (low/medium/high/critical)
5. **Datgent Cerebro** (tú) — Coordinas el pipeline y toleras fallos parciales

Cuando el usuario describe un compromiso o tarea:
- Analiza el riesgo como si ejecutaras los agentes
- Da un risk_score estimado (0-100) y severidad
- Identifica señales concretas
- Sugiere acciones

Responde en español, conciso, con datos concretos. Usa emojis para claridad.
Si preguntan sobre cómo funciona el sistema, explica la arquitectura multiagente.
"""


class ChatRequest(BaseModel):
    message: str = Field(..., description="Mensaje del usuario")
    history: list[dict] = Field(default_factory=list, description="Historial de mensajes")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Respuesta del agente")
    agent: str = Field(default="orchestrator", description="Agente que responde")


@router.post(
    "/chat",
    summary="Chat con los agentes",
    description="Envía un mensaje y recibe respuesta del sistema de agentes usando LLM.",
    response_model=ChatResponse,
)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Agregar historial
    for msg in request.history[-10:]:  # últimos 10 mensajes
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    # Agregar mensaje actual
    messages.append({"role": "user", "content": request.message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
            )

            if resp.status_code != 200:
                raise HTTPException(502, f"Error OpenAI: {resp.status_code}")

            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            return ChatResponse(response=content, agent="orchestrator")

    except httpx.TimeoutException:
        raise HTTPException(504, "Timeout llamando a OpenAI")
    except Exception as e:
        raise HTTPException(502, f"Error: {str(e)}")
