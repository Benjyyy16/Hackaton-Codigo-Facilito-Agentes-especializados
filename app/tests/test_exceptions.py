"""Tests de la traducción de errores de dominio a HTTP."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI, Query

from app.core.exceptions import (
    DomainError,
    DuplicateEventError,
    EntityNotFoundError,
    InvalidRequestError,
    JiraAuthError,
    JiraNotFoundError,
    JiraUnavailableError,
    SupabaseError,
    UnsupportedEventError,
    WebhookAuthError,
    register_exception_handlers,
)


def _app_raising(error: Exception) -> FastAPI:
    """App mínima cuya única ruta eleva el error indicado."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise error

    @app.get("/validated")
    async def validated(count: int = Query(ge=1)) -> dict[str, int]:
        return {"count": count}

    return app


async def _get(app: FastAPI, path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


class TestStatusMapping:
    """Cada error de dominio produce el código acordado en el diseño."""

    @pytest.mark.parametrize(
        ("error", "expected_status", "expected_code"),
        [
            (EntityNotFoundError(), 404, "not_found"),
            (DuplicateEventError(), 200, "duplicate_event"),
            (WebhookAuthError(), 401, "webhook_unauthorized"),
            (UnsupportedEventError(), 202, "unsupported_event"),
            (InvalidRequestError(), 422, "invalid_request"),
            (JiraAuthError(), 502, "jira_unauthorized"),
            (JiraNotFoundError(), 404, "jira_not_found"),
            (JiraUnavailableError(), 502, "jira_unavailable"),
            (SupabaseError(), 503, "supabase_error"),
        ],
    )
    async def test_domain_error_maps_to_status_and_code(
        self, error: DomainError, expected_status: int, expected_code: str
    ) -> None:
        response = await _get(_app_raising(error), "/boom")

        assert response.status_code == expected_status
        assert response.json()["error"]["code"] == expected_code


class TestResponseShape:
    async def test_body_is_uniform(self) -> None:
        response = await _get(_app_raising(EntityNotFoundError()), "/boom")

        body = response.json()
        assert set(body) == {"error"}
        assert set(body["error"]) == {"code", "message", "request_id", "details"}

    async def test_custom_message_and_details_are_preserved(self) -> None:
        error = EntityNotFoundError(
            "El evento no existe.", details={"event_id": "abc-123"}
        )

        response = await _get(_app_raising(error), "/boom")

        body = response.json()["error"]
        assert body["message"] == "El evento no existe."
        assert body["details"] == {"event_id": "abc-123"}


class TestUnexpectedErrors:
    async def test_internal_detail_is_not_exposed(self) -> None:
        """Un fallo no previsto no debe revelar nada del interior."""
        leaked = "connection string postgres://user:pw@host/db"

        response = await _get(_app_raising(RuntimeError(leaked)), "/boom")

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"
        assert leaked not in response.text


class TestRequestValidation:
    async def test_invalid_query_parameter_returns_422(self) -> None:
        response = await _get(_app_raising(EntityNotFoundError()), "/validated?count=0")

        assert response.status_code == 422
        body = response.json()["error"]
        assert body["code"] == "validation_error"
        assert body["details"]["fields"][0]["field"].endswith("count")

    async def test_rejected_value_is_not_echoed(self) -> None:
        """Una entrada rechazada puede contener datos sensibles."""
        response = await _get(
            _app_raising(EntityNotFoundError()), "/validated?count=sensitive-value"
        )

        assert response.status_code == 422
        assert "sensitive-value" not in response.text
