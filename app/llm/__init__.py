"""Capa LLM de Datgent.

Expone el proveedor real y la reserva determinística para que el sistema funcione
con o sin credenciales de OpenAI.
"""

from app.llm.base import (
    LLMError,
    LLMInvalidResponseError,
    LLMProvider,
    LLMResponse,
    LLMUnavailableError,
    NullLLMProvider,
)
from app.llm.openai_provider import OpenAILLMProvider
from app.llm.prompts import PROMPT_VERSION

__all__ = [
    "LLMError",
    "LLMInvalidResponseError",
    "LLMProvider",
    "LLMResponse",
    "LLMUnavailableError",
    "NullLLMProvider",
    "OpenAILLMProvider",
    "PROMPT_VERSION",
]
