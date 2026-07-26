"""Abstracciones de la capa LLM.

Se define como Protocol para no acoplar el orquestador a OpenAI: si mañana se usa
Anthropic o un modelo local, el contrato no cambia. ``NullLLMProvider`` existe para que
el sistema arranque sin credenciales y devuelva resultados determinísticos construidos
por reglas, no inventados.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.core.exceptions import DomainError


# --- Errores de dominio LLM -------------------------------------------------------
# Heredan de DomainError para que el handler global los traduzca a HTTP sin caso especial.


class LLMError(DomainError):
    """Raíz de errores de la capa LLM."""

    code: str = "llm_error"
    message: str = "Error en la capa de lenguaje."


class LLMUnavailableError(LLMError):
    """El proveedor no respondió tras agotar reintentos o sufrió timeout."""

    code = "llm_unavailable"
    status_code = 502
    message = "El modelo de lenguaje no está disponible en este momento."


class LLMInvalidResponseError(LLMError):
    """La respuesta del modelo no es JSON válido o no cumple el esquema esperado."""

    code = "llm_invalid_response"
    status_code = 502
    message = "El modelo devolvió una respuesta que no cumple el formato esperado."


# --- Modelo de respuesta -----------------------------------------------------------


class LLMResponse(BaseModel):
    """Respuesta normalizada de cualquier proveedor LLM.

    ``prompt_version`` viaja con la respuesta para que auditoría sepa qué prompt la generó.
    ``tokens_used`` y ``latency_ms`` permiten monitoreo de costos sin depender del proveedor.
    """

    content: dict[str, Any] | list[Any] | str
    model: str
    prompt_version: str
    tokens_used: int = Field(ge=0)
    latency_ms: float = Field(ge=0)


# --- Protocol del proveedor --------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """Contrato que debe cumplir cualquier proveedor LLM."""

    @property
    def name(self) -> str: ...

    def is_available(self) -> bool: ...

    async def complete(
        self,
        system: str,
        user: str,
        *,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse: ...


# --- Reserva determinística -------------------------------------------------------


class NullLLMProvider:
    """Proveedor de reserva cuando no hay API key configurada.

    Devuelve estructuras válidas construidas por reglas fijas. Nunca inventa datos ni
    llama a la red. ``is_available()`` retorna False para que los consumidores sepan
    que están operando en modo degradado.
    """

    @property
    def name(self) -> str:
        return "null"

    def is_available(self) -> bool:
        # Señala que NO hay LLM real disponible; el sistema opera en modo reserva.
        return False

    async def complete(
        self,
        system: str,
        user: str,
        *,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Genera respuesta determinística basada en reglas.

        Si se pide un ``response_model``, construye una instancia con valores por defecto
        de Pydantic. Si no, devuelve una estructura genérica de reserva que indica
        explícitamente que el análisis no fue realizado por un LLM.
        """
        from app.llm.prompts import PROMPT_VERSION

        if response_model is not None:
            # Construye la instancia con los defaults del modelo Pydantic.
            # Si el modelo no tiene defaults para campos requeridos, usa cadenas descriptivas.
            content = self._build_default_instance(response_model)
        else:
            content = {
                "status": "fallback",
                "message": "Análisis no disponible: sin proveedor LLM configurado.",
                "facts": [],
                "inferences": [],
                "assumptions": ["Se asume que no hay LLM disponible."],
            }

        return LLMResponse(
            content=content,
            model="null",
            prompt_version=PROMPT_VERSION,
            tokens_used=0,
            latency_ms=0.0,
        )

    @staticmethod
    def _build_default_instance(model: type[BaseModel]) -> dict[str, Any]:
        """Intenta construir una instancia con valores mínimos válidos.

        No inventa datos: usa defaults del modelo o cadenas que declaran la ausencia.
        """
        field_values: dict[str, Any] = {}
        for field_name, field_info in model.model_fields.items():
            if field_info.default is not None:
                field_values[field_name] = field_info.default
            elif field_info.default_factory is not None:
                field_values[field_name] = field_info.default_factory()
            else:
                # Campo requerido sin default: valor placeholder explícito según tipo.
                annotation = field_info.annotation
                if annotation is str or annotation == str:
                    field_values[field_name] = "No disponible (modo reserva)"
                elif annotation is int or annotation == int:
                    field_values[field_name] = 0
                elif annotation is float or annotation == float:
                    field_values[field_name] = 0.0
                elif annotation is bool or annotation == bool:
                    field_values[field_name] = False
                elif annotation is list or str(annotation).startswith("list"):
                    field_values[field_name] = []
                elif annotation is dict or str(annotation).startswith("dict"):
                    field_values[field_name] = {}
                else:
                    field_values[field_name] = None
        try:
            instance = model.model_validate(field_values)
            return instance.model_dump(mode="json")
        except Exception:
            # Si la validación falla, devuelve el dict crudo.
            return field_values
