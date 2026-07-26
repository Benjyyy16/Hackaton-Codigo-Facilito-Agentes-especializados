"""Tests de logging (RNF-2)."""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.core.logging import (
    REDACTED,
    RequestIdFilter,
    SecretRedactingFilter,
    configure_logging,
    get_logger,
    get_request_id,
    set_request_id,
)
from app.tests.conftest import VALID_SETTINGS


def _record(message: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=args or None,
        exc_info=None,
    )


class TestSecretRedaction:
    """RNF-2.3: los secretos no llegan a la salida de log."""

    def test_secret_in_message_is_redacted(self) -> None:
        secret = "super-secret-token"
        record = _record(f"llamando con token={secret}")

        SecretRedactingFilter([secret]).filter(record)

        assert secret not in record.getMessage()
        assert REDACTED in record.getMessage()

    def test_secret_in_arguments_is_redacted(self) -> None:
        """El caso realista: ``logger.info("token=%s", token)``."""
        secret = "super-secret-token"
        record = _record("token=%s", secret)

        SecretRedactingFilter([secret]).filter(record)

        assert secret not in record.getMessage()

    def test_secret_inside_dict_argument_is_redacted(self) -> None:
        secret = "super-secret-token"
        record = _record("payload=%s", {"Authorization": secret})

        SecretRedactingFilter([secret]).filter(record)

        assert secret not in record.getMessage()

    def test_short_values_are_not_redacted(self) -> None:
        """Redactar cadenas cortas convertiría texto legítimo en ruido."""
        record = _record("el estado es ok")

        SecretRedactingFilter(["ok"]).filter(record)

        assert record.getMessage() == "el estado es ok"

    def test_unrelated_message_is_untouched(self) -> None:
        record = _record("evento procesado correctamente")

        SecretRedactingFilter(["super-secret-token"]).filter(record)

        assert record.getMessage() == "evento procesado correctamente"

    def test_filter_built_from_settings_covers_every_secret(
        self, settings: Settings, caplog
    ) -> None:
        configure_logging(settings)
        handler = logging.getLogger().handlers[0]

        record = _record(
            "url=%s token=%s secret=%s",
            VALID_SETTINGS["SUPABASE_SERVICE_ROLE_KEY"],
            VALID_SETTINGS["JIRA_API_TOKEN"],
            VALID_SETTINGS["JIRA_WEBHOOK_SECRET"],
        )
        for log_filter in handler.filters:
            log_filter.filter(record)

        rendered = record.getMessage()
        assert VALID_SETTINGS["SUPABASE_SERVICE_ROLE_KEY"] not in rendered
        assert VALID_SETTINGS["JIRA_API_TOKEN"] not in rendered
        assert VALID_SETTINGS["JIRA_WEBHOOK_SECRET"] not in rendered


class TestRequestId:
    """RNF-2.2: correlación entre peticiones y sus tareas."""

    def test_absent_request_id_renders_as_dash(self) -> None:
        set_request_id(None)
        record = _record("sin contexto")

        RequestIdFilter().filter(record)

        assert record.request_id == "-"

    def test_request_id_is_attached_to_records(self) -> None:
        set_request_id("abc-123")
        record = _record("con contexto")

        RequestIdFilter().filter(record)

        assert record.request_id == "abc-123"
        set_request_id(None)

    def test_request_id_round_trip(self) -> None:
        set_request_id("xyz-789")
        assert get_request_id() == "xyz-789"
        set_request_id(None)
        assert get_request_id() is None


class TestConfiguration:
    def test_level_comes_from_settings(self) -> None:
        from app.tests.conftest import build_settings

        configure_logging(build_settings(LOG_LEVEL="WARNING"))

        assert logging.getLogger().level == logging.WARNING

    def test_configuring_twice_does_not_duplicate_handlers(
        self, settings: Settings
    ) -> None:
        configure_logging(settings)
        configure_logging(settings)

        assert len(logging.getLogger().handlers) == 1

    def test_logger_names_are_prefixed(self) -> None:
        assert get_logger("jira").name == "commitment_twin.jira"
