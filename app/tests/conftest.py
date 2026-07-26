"""Fixtures compartidas.

Los tests son herméticos (RNF-4.2). El repositorio contiene ``.env`` y ``.env.local``
reales, y el entorno de quien ejecuta puede tener variables exportadas; ambos falsearían un
test de configuración. De ahí las dos precauciones de este módulo:

* ``_isolate_environment`` limpia las variables del dominio de la aplicación.
* ``build_settings`` construye ``Settings`` con ``_env_file=None``, ignorando los archivos
  del repositorio.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from app.core.config import Settings, get_settings

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
