"""Tests del CORS aplicado en la aplicación.

Verifican que la política no se queda solo en ``app/core/security.py`` sino que llega al
middleware. Un ``cors_origins_for`` correcto y un ``create_app`` que lo ignora dejarían la
API abierta con la función de seguridad presente en el repositorio, que es la forma más
fácil de creer que algo está protegido cuando no lo está.
"""

from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware

from app.core.config import load_settings
from app.main import create_app

BASE_SETTINGS = {
    "_env_file": None,
    "SUPABASE_URL": "https://proyecto.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "clave-de-servicio",
}


def _cors_options(app) -> dict:
    """Extrae los argumentos con los que se montó el middleware de CORS."""
    for middleware in app.user_middleware:
        if middleware.cls is CORSMiddleware:
            return dict(middleware.kwargs)
    raise AssertionError("El middleware de CORS no está montado")


class TestCorsIsRestricted:
    def test_wildcard_origin_is_never_used(self) -> None:
        """``*`` con credenciales es inseguro y los navegadores lo rechazan."""
        app = create_app(load_settings(**BASE_SETTINGS, ENV="production", FRONTEND_URL="https://app.datgent.dev"))

        options = _cors_options(app)

        assert "*" not in options["allow_origins"]

    def test_production_allows_only_the_declared_frontend(self) -> None:
        app = create_app(
            load_settings(**BASE_SETTINGS, ENV="production", FRONTEND_URL="https://app.datgent.dev")
        )

        origins = _cors_options(app)["allow_origins"]

        assert origins == ["https://app.datgent.dev"]
        assert not any("localhost" in o for o in origins)

    def test_development_also_allows_localhost(self) -> None:
        app = create_app(
            load_settings(**BASE_SETTINGS, ENV="development", FRONTEND_URL="https://app.datgent.dev")
        )

        origins = _cors_options(app)["allow_origins"]

        assert "https://app.datgent.dev" in origins
        assert any("localhost" in o for o in origins)

    def test_missing_frontend_url_leaves_no_origin_allowed(self) -> None:
        """Un despliegue mal configurado falla visible en el navegador, no queda abierto.

        Caer a ``*`` cuando falta la configuración sería un valor por defecto inseguro: el
        despliegue funcionaría y nadie se enteraría de que la restricción no está.
        """
        app = create_app(load_settings(**BASE_SETTINGS, ENV="production", FRONTEND_URL=""))

        assert _cors_options(app)["allow_origins"] == []

    def test_headers_are_enumerated_not_wildcarded(self) -> None:
        app = create_app(
            load_settings(**BASE_SETTINGS, ENV="production", FRONTEND_URL="https://app.datgent.dev")
        )

        options = _cors_options(app)

        assert "*" not in options["allow_headers"]
        assert "Authorization" in options["allow_headers"]

    def test_methods_are_enumerated_not_wildcarded(self) -> None:
        """Enumerar los métodos impide que un verbo nuevo quede permitido sin revisarlo."""
        app = create_app(
            load_settings(**BASE_SETTINGS, ENV="production", FRONTEND_URL="https://app.datgent.dev")
        )

        methods = _cors_options(app)["allow_methods"]

        assert "*" not in methods
        assert "PUT" not in methods


class TestPortIsNotHardcoded:
    def test_render_start_command_uses_the_port_variable(self) -> None:
        """Render fija ``PORT`` y espera que el proceso escuche ahí."""
        from pathlib import Path

        render_yaml = Path(__file__).resolve().parents[2] / "render.yaml"
        content = render_yaml.read_text(encoding="utf-8")

        assert "$PORT" in content
