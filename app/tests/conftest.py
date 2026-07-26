"""Fixtures compartidas.

Los tests son herméticos (RNF-4.2). El repositorio contiene ``.env`` y ``.env.local``
reales, y el entorno de quien ejecuta puede tener variables exportadas; ambos falsearían un
test de configuración. De ahí las dos precauciones de este módulo:

* ``_isolate_environment`` limpia las variables del dominio de la aplicación.
* ``build_settings`` construye ``Settings`` con ``_env_file=None``, ignorando los archivos
  del repositorio.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.tests.fakes.supabase import FakeSupabaseClient

_MANAGED_PREFIXES = ("SUPABASE_", "JIRA_", "RISK_", "HTTP_")
_MANAGED_NAMES = ("ENV", "LOG_LEVEL")

VALID_SETTINGS: dict[str, Any] = {
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-key-for-tests",
    "JIRA_BASE_URL": "https://example.atlassian.net",
    "JIRA_EMAIL": "bot@example.com",
    "JIRA_API_TOKEN": "jira-api-token-for-tests",
    "JIRA_WEBHOOK_SECRET": "webhook-secret-for-tests",
    "ENV": "test",
}


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Retira del entorno las variables que la aplicación gestiona."""
    import os

    for name in list(os.environ):
        if name.startswith(_MANAGED_PREFIXES) or name in _MANAGED_NAMES:
            monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def build_settings(**overrides: Any) -> Settings:
    """Construye ``Settings`` válido, sin leer ningún archivo ``.env``."""
    values = {**VALID_SETTINGS, **overrides}
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.fixture
def settings() -> Settings:
    """Configuración válida para los tests que necesitan una."""
    return build_settings()


@pytest.fixture
def fake_supabase() -> FakeSupabaseClient:
    """Doble del cliente de Supabase."""
    return FakeSupabaseClient()


@pytest.fixture
def jira_http() -> Iterator[httpx.AsyncClient]:
    """Cliente HTTP de Jira sin red, que responde vacío a todo.

    La fixture ``app`` lo instala en ``app.state`` porque es lo que haría el ``lifespan``. Sin
    él, cualquier ruta que declare la dependencia del cliente de Jira fallaría antes incluso
    de validar el cuerpo de la petición, y un test de validación acabaría comprobando otra
    cosa.
    """
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={})),
        base_url="https://example.atlassian.net",
    )
    yield client


@pytest.fixture
def app(
    settings: Settings,
    fake_supabase: FakeSupabaseClient,
    jira_http: httpx.AsyncClient,
) -> FastAPI:
    """Aplicación lista para usar, con los clientes externos sustituidos.

    Se construye con ``create_app`` y luego se rellena ``app.state`` a mano, sin ejecutar el
    ``lifespan``: así ningún test intenta abrir una conexión real.
    """
    from app.main import create_app

    application = create_app(settings)
    application.state.supabase = fake_supabase
    application.state.jira_http = jira_http
    return application


@asynccontextmanager
async def client_for(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Cliente HTTP contra la app, sin red.

    ``raise_app_exceptions=False`` deja que los manejadores de excepción produzcan su
    respuesta en lugar de que la excepción salga hacia el test.
    """
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
