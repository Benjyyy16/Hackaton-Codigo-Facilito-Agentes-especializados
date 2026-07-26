"""Chat endpoint usando OpenAI para los agentes."""

from __future__ import annotations

from typing import Annotated

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_settings_dep
from app.core.config import Settings

router = APIRouter(prefix="/agents", tags=["agents-chat"])

OPENAI_API_KEY = os.environ.get(
    "OPENAI_API_KEY",
    "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",
)

SYSTEM_PROMPT = """Eres Datgent, un sistema de multi-agentes especializados en detección de riesgos de proyectos de software. 

Tienes 5 agentes internos:
1. **Commitment Agent** — Analiza vencimientos: detecta overdue, due_soon, no_due_date, reopened
2. **Technical Agent** — Detecta bloqueos, estancamiento, sin asignar, reasignaciones
3. **Financial Agent** — Calcula impacto económico: horas × costo/hora
4. **Risk Agent** — Compone score global 0-100 con severidad (low/medium/high/critical)
5. **Orchestrator** — Ejecuta el pipeline, tolera fallos parciales

Cuando el usuario describe un compromiso o tarea:
- Analiza el riesgo como si ejecutaras los agentes
- Da un risk_score estimado (0-100) y severidad
- Identifica señales concretas
- Sugiere acciones

Responde en español, conciso, con datos concretos. Usa emojis para claridad.
Si preguntan sobre cómo funciona el sistema, explica la arquitectura multi-agente.
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
