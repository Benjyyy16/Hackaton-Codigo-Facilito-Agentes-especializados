"""Proveedor LLM de OpenAI para Datgent.

Sigue el patrón del cliente Jira: httpx.AsyncClient de vida larga, reintentos con
backoff exponencial, respeto a Retry-After en 429, y errores de dominio en vez de
excepciones genéricas. Nunca registra la API key ni el prompt completo.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Final

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.logging import get_logger
from app.llm.base import LLMInvalidResponseError, LLMResponse, LLMUnavailableError
from app.llm.prompts import PROMPT_VERSION

logger = get_logger("llm.openai")

_OPENAI_CHAT_URL: Final[str] = "https://api.openai.com/v1/chat/completions"

#: Máximo de reintentos antes de declarar el servicio no disponible.
_MAX_RETRIES: Final[int] = 2

#: Espera base para backoff exponencial.
_RETRY_BASE_DELAY: Final[float] = 0.5

#: Techo de espera entre reintentos.
_MAX_RETRY_DELAY: Final[float] = 15.0

#: Códigos que NO se reintentan: credenciales inválidas.
_NO_RETRY_STATUSES: Final[frozenset[int]] = frozenset({401, 403})

#: Códigos que SÍ se reintentan.
_RETRYABLE_STATUSES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})

#: Regex para extraer JSON envuelto en ```json ... ```
_JSON_FENCE_RE: Final[re.Pattern[str]] = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL
)


class OpenAILLMProvider:
    """Proveedor de OpenAI con httpx, reintentos y parseo tolerante."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api_key: str | None = (
            settings.OPENAI_API_KEY.get_secret_value()
            if settings.OPENAI_API_KEY
            else None
        )
        self._model = settings.OPENAI_MODEL
        timeout_seconds = settings.OPENAI_TIMEOUT_SECONDS
        self._timeout = httpx.Timeout(
            connect=timeout_seconds,
            read=timeout_seconds,
            write=timeout_seconds,
            pool=timeout_seconds,
        )
        # El cliente se crea bajo demanda para no depender de un event loop en __init__.
        self._client: httpx.AsyncClient | None = None

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        # Sin API key no hay servicio; el sistema debe usar NullLLMProvider.
        return self._api_key is not None

    def _get_client(self) -> httpx.AsyncClient:
        """Crea o reutiliza el cliente HTTP. Lazy para evitar problemas con el event loop."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Cierra el cliente HTTP. Para uso en lifespan."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def complete(
        self,
        system: str,
        user: str,
        *,
        response_model: type[BaseModel] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """Envía prompt a OpenAI y devuelve respuesta parseada.

        Reintentos: máximo 2. 429 respeta Retry-After. 401/403 falla inmediato.
        El JSON se parsea de forma tolerante (acepta fences ```json```).
        Si se pasa response_model, valida la respuesta con Pydantic.
        """
        if not self.is_available():
            raise LLMUnavailableError("No hay API key de OpenAI configurada.")

        client = self._get_client()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start = time.perf_counter()
        response = await self._request_with_retries(client, headers, payload)
        latency_ms = (time.perf_counter() - start) * 1000

        # Extraer contenido de la respuesta.
        raw_content = self._extract_content(response)
        tokens_used = self._extract_tokens(response)

        # Parseo JSON tolerante.
        parsed = self._parse_json(raw_content)

        # Validación Pydantic si se pidió.
        if response_model is not None and isinstance(parsed, dict):
            try:
                instance = response_model.model_validate(parsed)
                parsed = instance.model_dump(mode="json")
            except ValidationError as exc:
                raise LLMInvalidResponseError(
                    f"La respuesta no cumple el esquema {response_model.__name__}.",
                    details={"validation_errors": str(exc.error_count())},
                ) from None

        return LLMResponse(
            content=parsed,
            model=self._model,
            prompt_version=PROMPT_VERSION,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )

    async def _request_with_retries(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Ejecuta la petición con reintentos y backoff."""
        last_response: httpx.Response | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.post(
                    _OPENAI_CHAT_URL, headers=headers, json=payload
                )
            except httpx.TimeoutException as exc:
                logger.warning("OpenAI timeout (intento %d/%d)", attempt + 1, _MAX_RETRIES + 1)
                if attempt >= _MAX_RETRIES:
                    raise LLMUnavailableError(
                        "OpenAI no respondió dentro del tiempo permitido."
                    ) from exc
                await asyncio.sleep(self._delay_for_attempt(attempt, None))
                continue
            except httpx.HTTPError as exc:
                logger.warning("OpenAI error de transporte: %s", type(exc).__name__)
                if attempt >= _MAX_RETRIES:
                    raise LLMUnavailableError(
                        "No se pudo contactar con OpenAI."
                    ) from exc
                await asyncio.sleep(self._delay_for_attempt(attempt, None))
                continue

            # Éxito.
            if resp.is_success:
                try:
                    return resp.json()
                except (ValueError, json.JSONDecodeError) as exc:
                    raise LLMInvalidResponseError(
                        "OpenAI devolvió una respuesta que no es JSON."
                    ) from exc

            # 401/403: no reintentar, credenciales inválidas.
            if resp.status_code in _NO_RETRY_STATUSES:
                # Log sin revelar la key.
                logger.error("OpenAI rechazó credenciales (status %d)", resp.status_code)
                raise LLMUnavailableError(
                    "OpenAI rechazó las credenciales configuradas.",
                    details={"status": resp.status_code},
                )

            # Códigos reintentables.
            if resp.status_code in _RETRYABLE_STATUSES:
                last_response = resp
                if attempt >= _MAX_RETRIES:
                    break
                delay = self._delay_for_attempt(attempt, resp)
                logger.warning(
                    "OpenAI %d, reintentando en %.1fs (intento %d/%d)",
                    resp.status_code,
                    delay,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                )
                await asyncio.sleep(delay)
                continue

            # Cualquier otro error: no reintentar.
            raise LLMUnavailableError(
                "OpenAI respondió con un error inesperado.",
                details={"status": resp.status_code},
            )

        # Reintentos agotados.
        status = last_response.status_code if last_response else None
        raise LLMUnavailableError(
            "OpenAI no respondió correctamente tras agotar reintentos.",
            details={"last_status": status},
        )

    @staticmethod
    def _delay_for_attempt(attempt: int, response: httpx.Response | None) -> float:
        """Calcula espera: Retry-After para 429, backoff exponencial para el resto."""
        if response is not None and response.status_code == 429:
            raw = response.headers.get("Retry-After")
            if raw:
                try:
                    advised = max(0.0, float(raw.strip()))
                    return min(advised, _MAX_RETRY_DELAY)
                except ValueError:
                    pass

        exponential = _RETRY_BASE_DELAY * (2 ** attempt)
        return min(exponential, _MAX_RETRY_DELAY)

    @staticmethod
    def _extract_content(response: dict[str, Any]) -> str:
        """Extrae el texto de la respuesta de OpenAI."""
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMInvalidResponseError(
                "La respuesta de OpenAI no tiene la estructura esperada."
            ) from exc

    @staticmethod
    def _extract_tokens(response: dict[str, Any]) -> int:
        """Extrae tokens usados; 0 si no está disponible."""
        usage = response.get("usage")
        if usage and isinstance(usage, dict):
            return usage.get("total_tokens", 0)
        return 0

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any] | list[Any] | str:
        """Parseo JSON tolerante: acepta fences ```json ... ``` y texto limpio."""
        text = raw.strip()

        # Intentar primero como JSON directo.
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass

        # Buscar JSON envuelto en fences de markdown.
        match = _JSON_FENCE_RE.search(text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except (json.JSONDecodeError, ValueError):
                pass

        # Si no se pudo parsear como JSON, devolver como string es un error.
        raise LLMInvalidResponseError(
            "No se pudo extraer JSON válido de la respuesta del modelo."
        )
