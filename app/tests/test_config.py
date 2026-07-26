"""Tests de configuración (RF-1)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.core.config import (
    ConfigurationError,
    Environment,
    LogLevel,
    Settings,
    get_settings,
    load_settings,
)
from app.tests.conftest import VALID_SETTINGS, build_settings


class TestRequiredVariables:
    """RF-1.2: falta una variable obligatoria y el arranque falla nombrándola.

    Solo las credenciales de Supabase son obligatorias. Las de cada provider son
    opcionales a propósito: un provider sin configurar no se registra, en lugar de
    impedir el arranque (ver ``build_provider_registry`` en ``app/main.py``).
    """

    @pytest.mark.parametrize(
        "missing",
        [
            "SUPABASE_URL",
            "SUPABASE_SERVICE_ROLE_KEY",
        ],
    )
    def test_missing_required_variable_is_reported_by_name(self, missing: str) -> None:
        values = {k: v for k, v in VALID_SETTINGS.items() if k != missing}

        with pytest.raises(ConfigurationError) as excinfo:
            load_settings(_env_file=None, **values)

        message = str(excinfo.value)
        assert missing in message
        assert "obligatoria ausente" in message

    @pytest.mark.parametrize(
        "optional",
        [
            "JIRA_BASE_URL",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
            "JIRA_WEBHOOK_SECRET",
        ],
    )
    def test_missing_provider_variable_still_starts(self, optional: str) -> None:
        """Un provider sin credenciales no impide arrancar: queda sin registrar."""
        values = {k: v for k, v in VALID_SETTINGS.items() if k != optional}

        settings = load_settings(_env_file=None, **values)

        assert getattr(settings, optional) is None

    def test_all_required_variables_present_succeeds(self) -> None:
        assert load_settings(_env_file=None, **VALID_SETTINGS)

    def test_error_message_does_not_leak_values(self) -> None:
        """RF-1.2: el mensaje nombra el campo, nunca el valor rechazado."""
        rejected = "super-secret-token-value"

        with pytest.raises(ConfigurationError) as excinfo:
            load_settings(
                _env_file=None, **{**VALID_SETTINGS, "JIRA_BASE_URL": rejected}
            )

        assert rejected not in str(excinfo.value)
        assert "JIRA_BASE_URL" in str(excinfo.value)


class TestSecretHandling:
    """RF-1.4 y RNF-1.1: los secretos no se filtran por representación."""

    def test_secrets_are_secretstr(self, settings: Settings) -> None:
        assert isinstance(settings.SUPABASE_SERVICE_ROLE_KEY, SecretStr)
        assert isinstance(settings.JIRA_API_TOKEN, SecretStr)
        assert isinstance(settings.JIRA_WEBHOOK_SECRET, SecretStr)

    def test_repr_does_not_expose_secret_values(self, settings: Settings) -> None:
        rendered = repr(settings) + str(settings)
        for secret in (
            VALID_SETTINGS["SUPABASE_SERVICE_ROLE_KEY"],
            VALID_SETTINGS["JIRA_API_TOKEN"],
            VALID_SETTINGS["JIRA_WEBHOOK_SECRET"],
        ):
            assert secret not in rendered

    def test_model_dump_does_not_expose_secret_values(self, settings: Settings) -> None:
        """Un volcado accidental a JSON tampoco debe revelar el secreto."""
        dumped = str(settings.model_dump())
        assert VALID_SETTINGS["JIRA_API_TOKEN"] not in dumped

    def test_secret_is_reachable_when_explicitly_revealed(
        self, settings: Settings
    ) -> None:
        """El valor sigue siendo utilizable donde hace falta de verdad."""
        assert (
            settings.JIRA_API_TOKEN.get_secret_value()
            == VALID_SETTINGS["JIRA_API_TOKEN"]
        )


class TestValidation:
    def test_url_without_scheme_is_rejected(self) -> None:
        with pytest.raises(Exception) as excinfo:
            build_settings(SUPABASE_URL="example.supabase.co")
        assert "URL absoluto" in str(excinfo.value)

    def test_trailing_slash_is_normalised(self) -> None:
        """Evita rutas con doble barra al concatenar."""
        result = build_settings(JIRA_BASE_URL="https://example.atlassian.net/")
        assert result.JIRA_BASE_URL == "https://example.atlassian.net"

    def test_email_without_at_is_rejected(self) -> None:
        with pytest.raises(Exception) as excinfo:
            build_settings(JIRA_EMAIL="not-an-email")
        assert "correo" in str(excinfo.value)

    @pytest.mark.parametrize("value", [-1, 101])
    def test_threshold_out_of_range_is_rejected(self, value: int) -> None:
        with pytest.raises(Exception):
            build_settings(RISK_ALERT_THRESHOLD=value)

    def test_timeout_must_be_positive(self) -> None:
        with pytest.raises(Exception):
            build_settings(HTTP_TIMEOUT_SECONDS=0)


class TestDefaults:
    def test_optional_values_have_sensible_defaults(self, settings: Settings) -> None:
        assert settings.RISK_ALERT_THRESHOLD == 70
        assert settings.HTTP_TIMEOUT_SECONDS == 10.0
        assert settings.HTTP_MAX_RETRIES == 3
        assert settings.LOG_LEVEL is LogLevel.INFO
        assert settings.SUPABASE_ANON_KEY is None

    def test_environment_flags(self) -> None:
        assert build_settings(ENV="production").is_production is True
        assert build_settings(ENV="development").is_production is False
        assert build_settings(ENV="test").ENV is Environment.TEST

    def test_metadata_is_exposed(self, settings: Settings) -> None:
        assert settings.app_name == "commitment-twin-backend"
        assert settings.app_version


class TestCaching:
    def test_settings_are_resolved_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name, value in VALID_SETTINGS.items():
            monkeypatch.setenv(name, str(value))
        get_settings.cache_clear()
        assert get_settings() is get_settings()
