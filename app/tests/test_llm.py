"""Tests de la capa LLM.

Sin red real: todo usa httpx.MockTransport. Verifica NullLLMProvider, OpenAILLMProvider,
parseo JSON, reintentos, backoff, sanitización de build_context y prompt_version.
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from app.llm.base import (
    LLMInvalidResponseError,
    LLMResponse,
    LLMUnavailableError,
    NullLLMProvider,
)
from app.llm.openai_provider import OpenAILLMProvider
from app.llm.prompts import (
    BUSINESS_EXPLANATION_SYSTEM,
    CAUSAL_CHAIN_SYSTEM,
    CORRELATION_SYSTEM,
    PREMORTEM_SYSTEM,
    PROMPT_VERSION,
    SCENARIOS_SYSTEM,
    build_context,
)


# --- Helpers -------------------------------------------------------------------


def _make_settings(**overrides: Any):
    """Construye Settings mínimos para tests sin tocar entorno real."""
    from pydantic import SecretStr

    from app.core.config import Settings

    defaults = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": SecretStr("fake-key"),
        "OPENAI_API_KEY": SecretStr("sk-test-key-123"),
        "OPENAI_MODEL": "gpt-4o-mini",
        "OPENAI_TIMEOUT_SECONDS": 5.0,
        "_env_file": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_settings_no_key(**overrides: Any):
    """Settings sin API key de OpenAI."""
    from pydantic import SecretStr

    from app.core.config import Settings

    defaults = {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": SecretStr("fake-key"),
        "OPENAI_API_KEY": None,
        "_env_file": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _openai_success_response(content: dict[str, Any] | str) -> dict[str, Any]:
    """Respuesta exitosa de OpenAI."""
    text = json.dumps(content) if isinstance(content, dict) else content
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"total_tokens": 150},
    }


def _mock_transport(handler):
    """Crea un MockTransport con el handler dado."""
    return httpx.MockTransport(handler)


# --- Tests NullLLMProvider ---------------------------------------------------------


class TestNullLLMProvider:
    """NullLLMProvider: reserva determinística sin red."""

    def test_is_available_returns_false(self):
        provider = NullLLMProvider()
        assert provider.is_available() is False

    def test_name_is_null(self):
        provider = NullLLMProvider()
        assert provider.name == "null"

    @pytest.mark.asyncio
    async def test_complete_returns_valid_llm_response(self):
        provider = NullLLMProvider()
        resp = await provider.complete("system", "user")
        assert isinstance(resp, LLMResponse)
        assert resp.model == "null"
        assert resp.tokens_used == 0
        assert resp.latency_ms == 0.0

    @pytest.mark.asyncio
    async def test_complete_includes_prompt_version(self):
        provider = NullLLMProvider()
        resp = await provider.complete("system", "user")
        assert resp.prompt_version == PROMPT_VERSION

    @pytest.mark.asyncio
    async def test_complete_without_model_returns_fallback_dict(self):
        provider = NullLLMProvider()
        resp = await provider.complete("system", "user")
        assert isinstance(resp.content, dict)
        assert resp.content["status"] == "fallback"

    @pytest.mark.asyncio
    async def test_complete_with_response_model_returns_valid_instance(self):
        from pydantic import BaseModel

        class SimpleModel(BaseModel):
            summary: str = "default summary"
            score: int = 42

        provider = NullLLMProvider()
        resp = await provider.complete("system", "user", response_model=SimpleModel)
        assert isinstance(resp.content, dict)
        assert resp.content["summary"] == "default summary"
        assert resp.content["score"] == 42


# --- Tests OpenAILLMProvider -------------------------------------------------------


class TestOpenAIProviderAvailability:
    """is_available según presencia de API key."""

    def test_available_with_key(self):
        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        assert provider.is_available() is True

    def test_not_available_without_key(self):
        settings = _make_settings_no_key()
        provider = OpenAILLMProvider(settings)
        assert provider.is_available() is False

    def test_name_is_openai(self):
        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        assert provider.name == "openai"


class TestOpenAIProviderSuccess:
    """Respuestas exitosas se parsean correctamente."""

    @pytest.mark.asyncio
    async def test_200_valid_json_parsed(self):
        content = {"summary": "test", "risk_score": 50}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_openai_success_response(content))

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        resp = await provider.complete("system", "user")
        assert resp.content == content
        assert resp.model == "gpt-4o-mini"
        assert resp.prompt_version == PROMPT_VERSION
        assert resp.tokens_used == 150

    @pytest.mark.asyncio
    async def test_json_wrapped_in_fence_parsed(self):
        """El modelo a veces envuelve la respuesta en ```json ... ```."""
        content = {"key": "value"}
        fenced = f"```json\n{json.dumps(content)}\n```"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_openai_success_response(fenced))

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        resp = await provider.complete("system", "user")
        assert resp.content == content

    @pytest.mark.asyncio
    async def test_json_wrapped_in_bare_fence_parsed(self):
        """Fence sin especificar lenguaje: ``` ... ```."""
        content = {"data": [1, 2, 3]}
        fenced = f"```\n{json.dumps(content)}\n```"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_openai_success_response(fenced))

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        resp = await provider.complete("system", "user")
        assert resp.content == content

    @pytest.mark.asyncio
    async def test_latency_recorded(self):
        content = {"ok": True}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_openai_success_response(content))

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        resp = await provider.complete("system", "user")
        assert resp.latency_ms >= 0


class TestOpenAIProviderErrors:
    """Errores y reintentos."""

    @pytest.mark.asyncio
    async def test_invalid_json_raises_invalid_response(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = {"choices": [{"message": {"content": "not json at all {"}}], "usage": {"total_tokens": 10}}
            return httpx.Response(200, json=body)

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        with pytest.raises(LLMInvalidResponseError):
            await provider.complete("system", "user")

    @pytest.mark.asyncio
    async def test_401_no_retry_raises_unavailable(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(401, json={"error": "invalid_api_key"})

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        with pytest.raises(LLMUnavailableError):
            await provider.complete("system", "user")

        # 401 no se reintenta: solo 1 llamada.
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_403_no_retry(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(403, json={"error": "forbidden"})

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        with pytest.raises(LLMUnavailableError):
            await provider.complete("system", "user")
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_429_retries_respecting_retry_after(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0.01"},
                    json={"error": "rate_limited"},
                )
            return httpx.Response(200, json=_openai_success_response({"ok": True}))

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        resp = await provider.complete("system", "user")
        assert resp.content == {"ok": True}
        assert call_count == 3  # 2 reintentos + 1 éxito

    @pytest.mark.asyncio
    async def test_500_retries_with_backoff(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return httpx.Response(500, json={"error": "internal"})
            return httpx.Response(200, json=_openai_success_response({"recovered": True}))

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        resp = await provider.complete("system", "user")
        assert resp.content == {"recovered": True}
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retries_exhausted_raises_unavailable(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(500, json={"error": "server_error"})

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        with pytest.raises(LLMUnavailableError):
            await provider.complete("system", "user")
        # 1 intento inicial + 2 reintentos = 3.
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_raises_unavailable(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout")

        settings = _make_settings(OPENAI_TIMEOUT_SECONDS=0.1)
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        with pytest.raises(LLMUnavailableError):
            await provider.complete("system", "user")

    @pytest.mark.asyncio
    async def test_no_api_key_raises_unavailable(self):
        settings = _make_settings_no_key()
        provider = OpenAILLMProvider(settings)

        with pytest.raises(LLMUnavailableError):
            await provider.complete("system", "user")

    @pytest.mark.asyncio
    async def test_response_model_validation_failure(self):
        """Si response_model falla validación -> LLMInvalidResponseError."""
        from pydantic import BaseModel, Field

        class StrictModel(BaseModel):
            score: int = Field(ge=0, le=100)
            name: str

        # Respuesta con score fuera de rango.
        content = {"score": 999, "name": "test"}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_openai_success_response(content))

        settings = _make_settings()
        provider = OpenAILLMProvider(settings)
        provider._client = httpx.AsyncClient(transport=_mock_transport(handler))

        with pytest.raises(LLMInvalidResponseError):
            await provider.complete("system", "user", response_model=StrictModel)


# --- Tests build_context y sanitización --------------------------------------------


class TestBuildContext:
    """build_context sanitiza secretos y construye contexto limpio."""

    def test_removes_token_key(self):
        data = {"title": "Compromiso A", "token": "sk-secret-123"}
        result = build_context(commitment=data)
        assert "sk-secret-123" not in result
        assert "token" not in result.lower().split('"')

    def test_removes_api_key(self):
        data = {"name": "test", "api_key": "super-secret"}
        result = build_context(metadata=data)
        assert "super-secret" not in result

    def test_removes_password(self):
        data = {"user": "admin", "password": "p4ssw0rd!"}
        result = build_context(metadata=data)
        assert "p4ssw0rd!" not in result

    def test_removes_nested_secrets(self):
        data = {"config": {"token": "nested-secret", "url": "https://api.com"}}
        result = build_context(metadata=data)
        assert "nested-secret" not in result
        assert "https://api.com" in result

    def test_removes_secrets_from_findings(self):
        findings = [
            {"code": "F1", "summary": "issue", "api_token": "token-xyz"},
            {"code": "F2", "credential": "cred-abc"},
        ]
        result = build_context(findings=findings)
        assert "token-xyz" not in result
        assert "cred-abc" not in result
        assert "F1" in result
        assert "F2" in result

    def test_preserves_safe_fields(self):
        commitment = {
            "title": "Entrega Q4",
            "due_date": "2024-12-31",
            "financial_exposure": "50000",
        }
        result = build_context(commitment=commitment)
        assert "Entrega Q4" in result
        assert "2024-12-31" in result
        assert "50000" in result

    def test_empty_context(self):
        result = build_context()
        assert "Sin contexto disponible" in result


# --- Tests de prompts y versión ----------------------------------------------------


class TestPrompts:
    """Los prompts existen, están versionados y exigen JSON."""

    def test_prompt_version_is_string(self):
        assert isinstance(PROMPT_VERSION, str)
        assert PROMPT_VERSION == "1.0"

    def test_all_prompts_exist(self):
        assert len(CORRELATION_SYSTEM) > 100
        assert len(CAUSAL_CHAIN_SYSTEM) > 100
        assert len(PREMORTEM_SYSTEM) > 100
        assert len(SCENARIOS_SYSTEM) > 100
        assert len(BUSINESS_EXPLANATION_SYSTEM) > 100

    def test_prompts_require_json_output(self):
        for prompt in [
            CORRELATION_SYSTEM,
            CAUSAL_CHAIN_SYSTEM,
            PREMORTEM_SYSTEM,
            SCENARIOS_SYSTEM,
            BUSINESS_EXPLANATION_SYSTEM,
        ]:
            assert "JSON" in prompt

    def test_prompts_require_facts_inferences_assumptions(self):
        for prompt in [
            CORRELATION_SYSTEM,
            CAUSAL_CHAIN_SYSTEM,
            PREMORTEM_SYSTEM,
            SCENARIOS_SYSTEM,
            BUSINESS_EXPLANATION_SYSTEM,
        ]:
            assert "facts" in prompt
            assert "inferences" in prompt
            assert "assumptions" in prompt

    def test_scenarios_prompt_has_three_kinds(self):
        assert "do_nothing" in SCENARIOS_SYSTEM
        assert "add_capacity" in SCENARIOS_SYSTEM
        assert "renegotiate_scope" in SCENARIOS_SYSTEM

    @pytest.mark.asyncio
    async def test_prompt_version_in_null_provider_response(self):
        """PROMPT_VERSION queda registrado en la respuesta del NullProvider."""
        provider = NullLLMProvider()
        resp = await provider.complete("sys", "usr")
        assert resp.prompt_version == PROMPT_VERSION
