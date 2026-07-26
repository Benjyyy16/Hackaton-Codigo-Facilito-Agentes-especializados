"""Tests del cliente de Jira (RF-3, RF-4.3).

Se usa ``httpx.MockTransport``, que ejercita la pila real de ``httpx`` sin red: los reintentos,
los timeouts y el manejo de estados se comprueban de verdad, no contra un doble del cliente.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import (
    JiraAuthError,
    JiraNotFoundError,
    JiraRateLimitError,
    JiraUnavailableError,
)
from app.integrations.jira.client import (
    MAX_RETRY_DELAY,
    SEARCH_JQL_PATH,
    JiraClient,
    close_jira_http_client,
    create_jira_http_client,
)
from app.tests.conftest import VALID_SETTINGS


@pytest.fixture(autouse=True)
def _no_real_sleeping(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Sustituye la espera entre reintentos y registra su duración.

    Sin esto, un test de reintentos tardaría segundos reales. Además permite afirmar sobre la
    espera aplicada, que es parte del contrato.
    """
    recorded: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr("app.integrations.jira.client.asyncio.sleep", _fake_sleep)
    return recorded


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_retries: int = 3,
    max_pages: int = 200,
) -> JiraClient:
    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://example.atlassian.net",
    )
    return JiraClient(http, max_retries=max_retries, max_pages=max_pages)


def _issue(key: str, issue_id: str = "1000") -> dict[str, object]:
    return {
        "id": issue_id,
        "key": key,
        "fields": {
            "summary": "Entrega",
            "updated": "2026-07-01T10:00:00.000+0000",
            "project": {"key": key.split("-")[0]},
        },
    }


class TestAuthentication:
    """RF-3.1."""

    async def test_basic_auth_header_is_sent(self, settings: Settings) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["authorization"] = request.headers.get("Authorization", "")
            return httpx.Response(200, json={"key": "DEMO"})

        http = create_jira_http_client(
            settings, transport=httpx.MockTransport(handler)
        )

        await JiraClient(http).get_project("DEMO")

        assert seen["authorization"].startswith("Basic ")

    def test_timeouts_are_explicit_on_every_phase(self, settings: Settings) -> None:
        """RF-3.2: sin timeout de escritura o de pool, una petición puede colgarse."""
        http = create_jira_http_client(settings)

        assert http.timeout.connect == settings.HTTP_TIMEOUT_SECONDS
        assert http.timeout.read == settings.HTTP_TIMEOUT_SECONDS
        assert http.timeout.write == settings.HTTP_TIMEOUT_SECONDS
        assert http.timeout.pool == settings.HTTP_TIMEOUT_SECONDS

    def test_base_url_comes_from_settings(self, settings: Settings) -> None:
        http = create_jira_http_client(settings)

        assert str(http.base_url).rstrip("/") == settings.JIRA_BASE_URL


class TestRateLimiting:
    """RF-3.3."""

    async def test_429_is_retried_and_then_succeeds(self) -> None:
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            if attempts["count"] == 1:
                return httpx.Response(429, headers={"Retry-After": "2"})
            return httpx.Response(200, json={"key": "DEMO"})

        result = await _client(handler).get_project("DEMO")

        assert attempts["count"] == 2
        assert result == {"key": "DEMO"}

    async def test_retry_after_header_is_honoured(
        self, _no_real_sleeping: list[float]
    ) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "7"})

        with pytest.raises(JiraRateLimitError):
            await _client(handler, max_retries=1).get_project("DEMO")

        assert _no_real_sleeping == [7.0]

    async def test_retry_after_is_capped(self, _no_real_sleeping: list[float]) -> None:
        """Un ``Retry-After`` desmesurado no debe bloquear la tarea indefinidamente."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "99999"})

        with pytest.raises(JiraRateLimitError):
            await _client(handler, max_retries=1).get_project("DEMO")

        assert _no_real_sleeping == [MAX_RETRY_DELAY]

    async def test_non_numeric_retry_after_falls_back_to_backoff(
        self, _no_real_sleeping: list[float]
    ) -> None:
        """``Retry-After`` admite fecha HTTP; en ese caso se usa espera exponencial."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
            )

        with pytest.raises(JiraRateLimitError):
            await _client(handler, max_retries=1).get_project("DEMO")

        assert _no_real_sleeping and _no_real_sleeping[0] > 0

    async def test_exhausted_retries_on_429_raise_rate_limit_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        with pytest.raises(JiraRateLimitError):
            await _client(handler, max_retries=2).get_project("DEMO")


class TestServerErrors:
    """RF-3.4 y RF-3.6."""

    async def test_500_is_retried_then_succeeds(self) -> None:
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            if attempts["count"] <= 2:
                return httpx.Response(500)
            return httpx.Response(200, json={"key": "DEMO"})

        await _client(handler).get_project("DEMO")

        assert attempts["count"] == 3

    async def test_backoff_grows_between_attempts(
        self, _no_real_sleeping: list[float]
    ) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        with pytest.raises(JiraUnavailableError):
            await _client(handler, max_retries=3).get_project("DEMO")

        assert len(_no_real_sleeping) == 3
        assert _no_real_sleeping[0] < _no_real_sleeping[-1]

    async def test_exhausted_retries_raise_unavailable(self) -> None:
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(502)

        with pytest.raises(JiraUnavailableError):
            await _client(handler, max_retries=2).get_project("DEMO")

        assert attempts["count"] == 3

    async def test_library_exception_does_not_escape(self) -> None:
        """RF-3.6: las capas superiores no deben ver excepciones de ``httpx``."""

        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("sin ruta al host")

        with pytest.raises(JiraUnavailableError):
            await _client(handler, max_retries=1).get_project("DEMO")

    async def test_timeout_is_retried_then_translated(self) -> None:
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            raise httpx.ReadTimeout("demasiado lento")

        with pytest.raises(JiraUnavailableError):
            await _client(handler, max_retries=2).get_project("DEMO")

        assert attempts["count"] == 3


class TestTerminalStatuses:
    """RF-3.5: lo que no se arregla reintentando, no se reintenta."""

    @pytest.mark.parametrize("status", [401, 403])
    async def test_auth_failures_are_not_retried(self, status: int) -> None:
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(status)

        with pytest.raises(JiraAuthError):
            await _client(handler).get_project("DEMO")

        assert attempts["count"] == 1

    async def test_missing_project_is_not_found(self) -> None:
        """RF-4.6."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        with pytest.raises(JiraNotFoundError):
            await _client(handler).get_project("NOPE")

    async def test_removed_endpoint_is_reported_clearly(self) -> None:
        """El endpoint clásico de búsqueda responde 410 desde su retirada."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                410, json={"errorMessages": ["The requested API has been removed."]}
            )

        with pytest.raises(JiraUnavailableError) as excinfo:
            await _client(handler).search_page("project = DEMO")

        assert "retirado" in str(excinfo.value)

    async def test_client_error_is_not_retried(self) -> None:
        attempts = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["count"] += 1
            return httpx.Response(400, json={"errorMessages": ["JQL inválido"]})

        with pytest.raises(JiraUnavailableError):
            await _client(handler).search_page("jql roto")

        assert attempts["count"] == 1

    async def test_non_json_body_is_translated(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>error</html>")

        with pytest.raises(JiraUnavailableError):
            await _client(handler).get_project("DEMO")

    async def test_unexpected_body_shape_is_translated(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["no", "es", "un", "objeto"])

        with pytest.raises(JiraUnavailableError):
            await _client(handler).get_project("DEMO")


class TestSearchRequest:
    async def test_uses_the_current_jql_endpoint(self) -> None:
        """El endpoint clásico está retirado; debe usarse ``/search/jql``."""
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            return httpx.Response(200, json={"issues": [], "isLast": True})

        await _client(handler).search_page("project = DEMO")

        assert seen["path"] == SEARCH_JQL_PATH

    async def test_first_page_omits_the_page_token(self) -> None:
        """Enviar ``nextPageToken`` en la primera llamada devuelve 400."""
        seen: dict[str, str | None] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["token"] = request.url.params.get("nextPageToken")
            return httpx.Response(200, json={"issues": [], "isLast": True})

        await _client(handler).search_page("project = DEMO")

        assert seen["token"] is None

    async def test_subsequent_page_sends_the_token(self) -> None:
        seen: dict[str, str | None] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["token"] = request.url.params.get("nextPageToken")
            return httpx.Response(200, json={"issues": [], "isLast": True})

        await _client(handler).search_page("project = DEMO", next_page_token="tok-2")

        assert seen["token"] == "tok-2"

    async def test_fields_are_requested_explicitly(self) -> None:
        """El endpoint nuevo devuelve un conjunto mínimo si no se piden campos."""
        seen: dict[str, str | None] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["fields"] = request.url.params.get("fields")
            return httpx.Response(200, json={"issues": [], "isLast": True})

        await _client(handler).search_page("project = DEMO")

        assert seen["fields"] is not None
        for expected in ("summary", "status", "duedate", "timeoriginalestimate"):
            assert expected in seen["fields"]


class TestIssueIteration:
    """RF-4.3: la paginación queda encapsulada."""

    async def test_pages_are_traversed_until_is_last(self) -> None:
        pages = [
            {"issues": [_issue("DEMO-1")], "nextPageToken": "t1", "isLast": False},
            {"issues": [_issue("DEMO-2")], "nextPageToken": "t2", "isLast": False},
            {"issues": [_issue("DEMO-3")], "isLast": True},
        ]
        calls = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            payload = pages[calls["count"]]
            calls["count"] += 1
            return httpx.Response(200, json=payload)

        collected = [
            issue async for issue in _client(handler).iter_issues("project = DEMO")
        ]

        assert [item["key"] for item in collected] == ["DEMO-1", "DEMO-2", "DEMO-3"]
        assert calls["count"] == 3

    async def test_iteration_stops_without_page_token(self) -> None:
        """Sin ``isLast`` pero sin token, no hay más páginas que pedir."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"issues": [_issue("DEMO-1")]})

        collected = [
            issue async for issue in _client(handler).iter_issues("project = DEMO")
        ]

        assert len(collected) == 1

    async def test_empty_page_ends_iteration(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"issues": [], "nextPageToken": "t1"})

        collected = [
            issue async for issue in _client(handler).iter_issues("project = DEMO")
        ]

        assert collected == []

    async def test_repeated_token_breaks_the_loop(self) -> None:
        """Defensa contra el encadenamiento infinito documentado en este endpoint."""

        def handler(_request: httpx.Request) -> httpx.Response:
            # Siempre el mismo token y nunca ``isLast``: el bucle sería infinito.
            return httpx.Response(
                200,
                json={
                    "issues": [_issue("DEMO-1")],
                    "nextPageToken": "siempre-el-mismo",
                    "isLast": False,
                },
            )

        collected = [
            issue async for issue in _client(handler).iter_issues("project = DEMO")
        ]

        assert len(collected) == 2

    async def test_page_cap_bounds_the_traversal(self) -> None:
        """Segunda defensa: tokens distintos cada vez y ``isLast`` siempre falso."""
        counter = {"n": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            counter["n"] += 1
            return httpx.Response(
                200,
                json={
                    "issues": [_issue(f"DEMO-{counter['n']}")],
                    "nextPageToken": f"token-{counter['n']}",
                    "isLast": False,
                },
            )

        collected = [
            issue
            async for issue in _client(handler, max_pages=5).iter_issues("project = DEMO")
        ]

        assert len(collected) == 5

    async def test_max_issues_limit_is_respected(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "issues": [_issue(f"DEMO-{n}", str(n)) for n in range(10)],
                    "nextPageToken": "next",
                    "isLast": False,
                },
            )

        collected = [
            issue
            async for issue in _client(handler).iter_issues("project = DEMO", max_issues=3)
        ]

        assert len(collected) == 3

    async def test_failure_mid_iteration_propagates_as_domain_error(self) -> None:
        calls = {"count": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            calls["count"] += 1
            if calls["count"] == 1:
                return httpx.Response(
                    200,
                    json={
                        "issues": [_issue("DEMO-1")],
                        "nextPageToken": "t1",
                        "isLast": False,
                    },
                )
            return httpx.Response(401)

        client = _client(handler)
        with pytest.raises(JiraAuthError):
            async for _ in client.iter_issues("project = DEMO"):
                pass


class TestSecretHygiene:
    """RF-3.7: el token no debe aparecer en los logs."""

    async def test_logs_do_not_contain_the_token(
        self, settings: Settings, caplog: pytest.LogCaptureFixture
    ) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"key": "DEMO"})

        http = create_jira_http_client(
            settings, transport=httpx.MockTransport(handler)
        )

        with caplog.at_level("DEBUG"):
            await JiraClient(http).get_project("DEMO")

        assert VALID_SETTINGS["JIRA_API_TOKEN"] not in caplog.text

    async def test_error_details_do_not_contain_the_token(
        self, settings: Settings
    ) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401)

        http = create_jira_http_client(
            settings, transport=httpx.MockTransport(handler)
        )

        with pytest.raises(JiraAuthError) as excinfo:
            await JiraClient(http).get_project("DEMO")

        rendered = f"{excinfo.value} {excinfo.value.details}"
        assert VALID_SETTINGS["JIRA_API_TOKEN"] not in rendered


class TestShutdown:
    async def test_client_is_closed(self, settings: Settings) -> None:
        http = create_jira_http_client(settings)

        await close_jira_http_client(http)

        assert http.is_closed

    async def test_closing_none_is_a_no_op(self) -> None:
        await close_jira_http_client(None)

    async def test_failure_while_closing_does_not_propagate(self) -> None:
        class Failing:
            async def aclose(self) -> None:
                raise RuntimeError("ya estaba cerrado")

        await close_jira_http_client(Failing())  # type: ignore[arg-type]


class TestProviderLifecycle:
    """El provider de Jira gestiona su cliente HTTP de vida larga."""

    async def test_connect_creates_the_client_and_close_releases_it(
        self, settings: Settings
    ) -> None:
        from app.providers.jira import JiraProvider

        provider = JiraProvider(settings)
        await provider.connect()
        http = provider._http  # noqa: SLF001

        assert isinstance(http, httpx.AsyncClient)
        assert not http.is_closed

        await provider.close()
        assert http.is_closed

    async def test_connect_is_idempotent(self, settings: Settings) -> None:
        """El registro puede conectar dos veces sin duplicar conexiones."""
        from app.providers.jira import JiraProvider

        provider = JiraProvider(settings)
        await provider.connect()
        first = provider._http  # noqa: SLF001
        await provider.connect()

        assert provider._http is first  # noqa: SLF001
        await provider.close()

    async def test_health_before_connect_is_unknown(self, settings: Settings) -> None:
        """No haber comprobado no es lo mismo que estar caído."""
        from app.providers.jira import JiraProvider
        from app.schemas.common import DependencyStatus

        health = await JiraProvider(settings).health()

        assert health.status is DependencyStatus.UNKNOWN

    async def test_health_reports_up_when_jira_answers(self, settings: Settings) -> None:
        from app.providers.jira import JiraProvider
        from app.schemas.common import DependencyStatus

        transport = httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"accountId": "abc"})
        )
        provider = JiraProvider(settings, transport=transport)
        await provider.connect()

        health = await provider.health()

        assert health.status is DependencyStatus.UP
        assert health.latency_ms is not None
        await provider.close()

    async def test_health_reports_down_without_raising(self, settings: Settings) -> None:
        """``health()`` informa, no eleva (RF-2.3)."""
        from app.providers.jira import JiraProvider
        from app.schemas.common import DependencyStatus

        transport = httpx.MockTransport(lambda _request: httpx.Response(500))
        provider = JiraProvider(settings, transport=transport, )
        await provider.connect()

        health = await provider.health()

        assert health.status is DependencyStatus.DOWN
        assert health.detail
        await provider.close()

    async def test_operations_before_connect_fail_loudly(
        self, settings: Settings
    ) -> None:
        """Mejor un error claro que un ``NoneType`` en mitad de una sincronización."""
        from app.providers.jira import JiraProvider

        with pytest.raises(RuntimeError, match="connect"):
            await JiraProvider(settings).ensure_workspace_exists("DEMO")
