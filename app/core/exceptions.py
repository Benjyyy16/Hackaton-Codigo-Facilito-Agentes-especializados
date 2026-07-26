"""Errores de dominio y su traducción a HTTP.

El dominio no conoce HTTP: eleva excepciones con significado de negocio. La correspondencia
con códigos de estado vive en un único lugar, ``register_exception_handlers``, que se
registra en la app. Así ninguna ruta necesita construir ``HTTPException`` a mano y el mapeo
no se dispersa por el proyecto.

El cuerpo de error es uniforme y nunca incluye detalle interno ni valores de configuración
(RNF-1.1).
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.logging import get_logger, get_request_id

logger = get_logger("errors")


class ErrorBody(BaseModel):
    """Detalle del error."""

    code: str = Field(description="Identificador estable del tipo de error.")
    message: str = Field(description="Descripción apta para mostrar al consumidor.")
    request_id: str | None = Field(
        default=None, description="Identificador de correlación de la petición."
    )
    details: dict[str, Any] | None = Field(
        default=None, description="Contexto adicional seguro de exponer."
    )


class ErrorResponse(BaseModel):
    """Envoltura uniforme de error para toda la API."""

    error: ErrorBody


# --- Jerarquía de dominio ---------------------------------------------------------


class DomainError(Exception):
    """Raíz de los errores de dominio."""

    code: str = "domain_error"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Error interno."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class EntityNotFoundError(DomainError):
    """La entidad solicitada no existe o está borrada lógicamente."""

    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND
    message = "El recurso solicitado no existe."


class DuplicateEventError(DomainError):
    """El evento ya se había recibido.

    No es un fallo: es el resultado esperado de la deduplicación. El manejador lo traduce a
    una respuesta de éxito marcada como duplicada (RF-5.5, RF-6.4).
    """

    code = "duplicate_event"
    status_code = status.HTTP_200_OK
    message = "El evento ya había sido registrado."


class WebhookAuthError(DomainError):
    """El secreto compartido del webhook falta o no coincide."""

    code = "webhook_unauthorized"
    status_code = status.HTTP_401_UNAUTHORIZED
    message = "Secreto de webhook inválido."


class UnsupportedEventError(DomainError):
    """El tipo de evento de Jira no está soportado y se descarta de forma explícita."""

    code = "unsupported_event"
    status_code = status.HTTP_202_ACCEPTED
    message = "Tipo de evento no soportado; se descarta."


class InvalidRequestError(DomainError):
    """La combinación de parámetros no es válida para la operación."""

    code = "invalid_request"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    message = "La petición no es válida."


# --- Integraciones ----------------------------------------------------------------


class IntegrationError(DomainError):
    """Fallo al hablar con un sistema externo."""

    code = "integration_error"
    status_code = status.HTTP_502_BAD_GATEWAY
    message = "Un sistema externo no respondió correctamente."


class JiraError(IntegrationError):
    """Raíz de los fallos de Jira."""

    code = "jira_error"


class JiraAuthError(JiraError):
    """Jira rechazó las credenciales. No se reintenta (RF-3.5)."""

    code = "jira_unauthorized"
    status_code = status.HTTP_502_BAD_GATEWAY
    message = "Jira rechazó las credenciales configuradas."


class JiraNotFoundError(JiraError):
    """El recurso pedido no existe en Jira."""

    code = "jira_not_found"
    status_code = status.HTTP_404_NOT_FOUND
    message = "El recurso no existe en Jira."


class JiraUnavailableError(JiraError):
    """Jira no respondió tras agotar los reintentos (RF-3.6)."""

    code = "jira_unavailable"
    status_code = status.HTTP_502_BAD_GATEWAY
    message = "Jira no está disponible en este momento."


class JiraRateLimitError(JiraError):
    """Jira aplicó límite de tasa y los reintentos no bastaron (RF-3.3)."""

    code = "jira_rate_limited"
    status_code = status.HTTP_502_BAD_GATEWAY
    message = "Jira está aplicando límite de tasa."


class SupabaseError(IntegrationError):
    """Fallo al operar contra Supabase (RF-7.5)."""

    code = "supabase_error"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "El almacenamiento no está disponible en este momento."


# --- Traducción a HTTP ------------------------------------------------------------

_SERVER_ERROR_THRESHOLD: Final[int] = 500


def _build_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=get_request_id(),
            details=details,
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    """Registra la única traducción de errores de dominio a respuestas HTTP."""

    @app.exception_handler(DomainError)
    async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        if exc.status_code >= _SERVER_ERROR_THRESHOLD:
            logger.error("Error de dominio: %s", exc.code, exc_info=exc)
        else:
            logger.info("Error de dominio: %s", exc.code)
        return _build_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Se conservan campo y motivo, no el valor recibido: una entrada rechazada puede
        # contener datos sensibles.
        fields = [
            {
                "field": ".".join(str(part) for part in item["loc"]),
                "reason": item["msg"],
            }
            for item in exc.errors()
        ]
        return _build_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Los parámetros de la petición no son válidos.",
            details={"fields": fields},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Se registra con traza, pero al cliente solo llega un mensaje genérico: cualquier
        # detalle interno podría revelar estructura o configuración.
        logger.error("Error no controlado", exc_info=exc)
        return _build_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Error interno del servidor.",
        )
