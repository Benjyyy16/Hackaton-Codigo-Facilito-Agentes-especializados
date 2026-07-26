"""Configuración central de logging.

Dos garantías (RNF-2.1, RNF-2.3):

* Cada línea lleva el identificador de correlación de la petición que la originó, de forma
  que los registros de una petición y los de su tarea en segundo plano se puedan enlazar.
* Los valores secretos conocidos se redactan antes de escribirse. Es una segunda barrera; la
  primera es que los secretos son ``SecretStr`` y no se imprimen solos.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any, Final

from pydantic import SecretStr

from app.core.config import Settings

REDACTED: Final[str] = "***REDACTED***"
_MIN_REDACTABLE_LENGTH: Final[int] = 8

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(value: str | None) -> None:
    """Fija el identificador de correlación del contexto actual."""
    _request_id.set(value)


def get_request_id() -> str | None:
    """Devuelve el identificador de correlación del contexto actual, si hay alguno."""
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    """Inyecta ``request_id`` en cada registro para que el formateador pueda usarlo."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class SecretRedactingFilter(logging.Filter):
    """Sustituye valores secretos por un marcador en el mensaje y en sus argumentos.

    Los secretos muy cortos se ignoran a propósito: redactar una cadena de dos o tres
    caracteres produciría un ruido enorme sobre texto legítimo.
    """

    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = [s for s in secrets if s and len(s) >= _MIN_REDACTABLE_LENGTH]

    def _scrub(self, value: Any) -> Any:
        if isinstance(value, str):
            for secret in self._secrets:
                if secret in value:
                    value = value.replace(secret, REDACTED)
            return value
        if isinstance(value, tuple):
            return tuple(self._scrub(item) for item in value)
        if isinstance(value, dict):
            return {key: self._scrub(item) for key, item in value.items()}
        return value

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        if isinstance(record.msg, str):
            record.msg = self._scrub(record.msg)
        if record.args:
            record.args = self._scrub(record.args)  # type: ignore[assignment]
        return True


def _collect_secret_values(settings: Settings) -> list[str]:
    """Reúne los valores secretos de la configuración para poder redactarlos."""
    values: list[str] = []
    for value in vars(settings).values():
        if isinstance(value, SecretStr):
            revealed = value.get_secret_value()
            if revealed:
                values.append(revealed)
    return values


def configure_logging(settings: Settings) -> None:
    """Instala la configuración de logging del proceso.

    Es idempotente: los manejadores previos se retiran, de modo que llamarla dos veces (por
    ejemplo en tests) no duplica la salida.
    """
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s [%(name)s] [req=%(request_id)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.addFilter(RequestIdFilter())
    handler.addFilter(SecretRedactingFilter(_collect_secret_values(settings)))

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.value)

    # Uvicorn instala sus propios manejadores; delegar en la raíz evita la línea duplicada.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger con el prefijo de la aplicación."""
    return logging.getLogger(f"commitment_twin.{name}")
