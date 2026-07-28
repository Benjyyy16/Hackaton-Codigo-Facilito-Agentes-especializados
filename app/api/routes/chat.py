"""Chat endpoint usando OpenAI para los agentes."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter(prefix="/agents", tags=["agents-chat"])

SYSTEM_PROMPT = """Eres Datgent Cerebro, IA empresarial multiagente.

Regla principal: responde exactamente lo que el usuario solicita en su último mensaje.
No fuerces análisis de riesgo si el usuario pidió redactar, resumir, explicar, responder
un correo, preparar una respuesta comercial, crear tareas, priorizar o preguntar algo general.

Usa el contexto recibido sólo si ayuda. Si falta un dato imprescindible, pide ese dato.
Si el usuario pega un mensaje de otra persona, redacta una respuesta lista para enviar.
Cuando aplique, puedes apoyarte en agentes internos: Estratega, Auditor, Builder, Reviewer.

Responde en español, claro, concreto y accionable. Sin relleno.
"""

FALLBACK_MODEL = "gpt-4o-mini"


class ChatRequest(BaseModel):
    message: str = Field(..., description="Mensaje del usuario")
    history: list[dict] = Field(default_factory=list, description="Historial de mensajes")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Respuesta del agente")
    agent: str = Field(default="datgent", description="Agente que responde")


def _extract_response_text(data: dict) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for item in data.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text

    return "No pude generar una respuesta."


@router.post(
    "/chat",
    summary="Chat con los agentes",
    description="Envía un mensaje y recibe respuesta del sistema de agentes usando LLM.",
    response_model=ChatResponse,
)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    settings = get_settings()
    api_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
    if not api_key:
        raise HTTPException(503, "OPENAI_API_KEY no configurada")

    messages = []

    # Agregar historial
    for msg in request.history[-10:]:  # últimos 10 mensajes
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    # Agregar mensaje actual
    messages.append({"role": "user", "content": request.message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            models = [settings.OPENAI_MODEL]
            if FALLBACK_MODEL not in models:
                models.append(FALLBACK_MODEL)

            for model in models:
                resp = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "instructions": SYSTEM_PROMPT,
                        "input": messages,
                        "max_output_tokens": 350,
                    },
                )

                if resp.status_code != 400:
                    break

            if resp.status_code != 200:
                raise HTTPException(502, f"Error OpenAI: {resp.status_code}")

            data = resp.json()
            content = _extract_response_text(data)

            return ChatResponse(response=content, agent="datgent")

    except httpx.TimeoutException:
        raise HTTPException(504, "Timeout llamando a OpenAI")
    except Exception as e:
        raise HTTPException(502, f"Error: {str(e)}")
