"""Tests del health check y de la app factory (RF-2, RNF-2.2)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI

from app.core.config import Settings
from app.main import REQUEST_ID_HEADER, create_app
from app.schemas.common import DependencyStatus, ServiceStatus
from app.services.health_service import HealthService
from app.tests.conftest import VALID_SETTINGS, client_for
from app.tests.fakes.supabase import FakeSupabaseClient


class TestHealthyService:
    async def test_returns_200_with_service_metadata(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """RF-2.1."""
        fake_supabase.for_table("projects").returns([])

        async with client_for(app) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == ServiceStatus.OK
        assert body["service"] == "commitment-twin-backend"
        assert body["version"]
        assert body["environment"] == "test"

    async def test_reports_dependency_as_up(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        fake_supabase.for_table("projects").returns([])

        async with client_for(app) as client:
            response = await client.get("/health")

        dependency = response.json()["dependencies"][0]
        assert dependency["name"] == "supabase"
        assert dependency["status"] == DependencyStatus.UP
        assert dependency["latency_ms"] is not None


class TestDegradedService:
    """RF-2.3: una dependencia caída degrada, no rompe."""

    async def test_returns_200_when_supabase_is_down(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        fake_supabase.for_table("projects").raises(ConnectionError("sin ruta al host"))

        async with client_for(app) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == ServiceStatus.DEGRADED
        assert body["dependencies"][0]["status"] == DependencyStatus.DOWN

    async def test_missing_client_is_unknown_not_down(
        self, settings: Settings
    ) -> None:
        """No haber podido comprobar no es lo mismo que estar caído."""
        app = create_app(settings)
        app.state.supabase = None

        async with client_for(app) as client:
            response = await client.get("/health")

        body = response.json()
        assert response.status_code == 200
        assert body["dependencies"][0]["status"] == DependencyStatus.UNKNOWN
        assert body["status"] == ServiceStatus.OK


class TestProbeTimeout:
    """RF-2.4: la comprobación no puede colgar el endpoint."""

    async def test_slow_dependency_is_reported_as_down(
        self, settings: Settings
    ) -> None:
        class SlowClient:
            def table(self, _name: str) -> "SlowClient":
                return self

            def select(self, *_a: object, **_kw: object) -> "SlowClient":
                return self

            def limit(self, *_a: object) -> "SlowClient":
                return self

            async def execute(self) -> None:
                await asyncio.sleep(10)

        service = HealthService(settings, SlowClient(), probe_timeout=0.05)

        result = await service.check()

        assert result.status is ServiceStatus.DEGRADED
        assert result.dependencies[0].status is DependencyStatus.DOWN

    async def test_probe_respects_its_budget(self, settings: Settings) -> None:
        class SlowClient:
            def table(self, _name: str) -> "SlowClient":
                return self

            def select(self, *_a: object, **_kw: object) -> "SlowClient":
                return self

            def limit(self, *_a: object) -> "SlowClient":
                return self

            async def execute(self) -> None:
                await asyncio.sleep(10)

        service = HealthService(settings, SlowClient(), probe_timeout=0.05)

        started = asyncio.get_running_loop().time()
        await service.check()
        elapsed = asyncio.get_running_loop().time() - started

        assert elapsed < 1.0


class TestNoSensitiveData:
    """RF-2.2 y RNF-1.2: el health check no expone configuración."""

    async def test_response_contains_no_secret_values(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        fake_supabase.for_table("projects").returns([])

        async with client_for(app) as client:
            response = await client.get("/health")

        for secret in (
            VALID_SETTINGS["SUPABASE_SERVICE_ROLE_KEY"],
            VALID_SETTINGS["JIRA_API_TOKEN"],
            VALID_SETTINGS["JIRA_WEBHOOK_SECRET"],
        ):
            assert secret not in response.text

    async def test_response_does_not_expose_urls(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        fake_supabase.for_table("projects").returns([])

        async with client_for(app) as client:
            response = await client.get("/health")

        assert VALID_SETTINGS["SUPABASE_URL"] not in response.text

    async def test_health_requires_no_authentication(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        fake_supabase.for_table("projects").returns([])

        async with client_for(app) as client:
            response = await client.get("/health")

        assert response.status_code == 200


class TestRequestCorrelation:
    """RNF-2.2."""

    async def test_response_carries_a_request_id(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        fake_supabase.for_table("projects").returns([])

        async with client_for(app) as client:
            response = await client.get("/health")

        assert response.headers[REQUEST_ID_HEADER]

    async def test_client_supplied_request_id_is_preserved(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        """Mantiene la traza cuando la petición atraviesa varios servicios."""
        fake_supabase.for_table("projects").returns([])

        async with client_for(app) as client:
            response = await client.get(
                "/health", headers={REQUEST_ID_HEADER: "trace-abc-123"}
            )

        assert response.headers[REQUEST_ID_HEADER] == "trace-abc-123"

    async def test_each_request_gets_its_own_id(
        self, app: FastAPI, fake_supabase: FakeSupabaseClient
    ) -> None:
        fake_supabase.for_table("projects").returns([])

        async with client_for(app) as client:
            first = await client.get("/health")
            second = await client.get("/health")

        assert first.headers[REQUEST_ID_HEADER] != second.headers[REQUEST_ID_HEADER]


class TestAppFactory:
    def test_settings_are_injectable(self, settings: Settings) -> None:
        """Permite construir la app sin depender del entorno del proceso."""
        app = create_app(settings)

        assert app.state.settings is settings

    def test_openapi_is_generated(self, settings: Settings) -> None:
        """RNF-4.4."""
        schema = create_app(settings).openapi()

        assert "/health" in schema["paths"]
        assert schema["info"]["title"] == "Commitment Twin API"

    def test_lifespan_is_configured_not_deprecated_events(
        self, settings: Settings
    ) -> None:
        """El scaffold anterior usaba ``@app.on_event``, que está obsoleto."""
        app = create_app(settings)

        assert app.router.lifespan_context is not None
        assert app.router.on_startup == []
        assert app.router.on_shutdown == []


class TestLifespan:
    async def test_startup_survives_supabase_failure(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Abortar el arranque dejaría al operador sin poder consultar qué falla."""
        from app import main as main_module

        async def _fail(_settings: Settings) -> None:
            raise RuntimeError("credenciales rechazadas")

        monkeypatch.setattr(main_module, "create_supabase_client", _fail)
        app = create_app(settings)

        async with app.router.lifespan_context(app):
            assert app.state.supabase is None

    async def test_client_is_released_on_shutdown(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app import main as main_module

        fake = FakeSupabaseClient()
        closed: list[object] = []

        async def _create(_settings: Settings) -> FakeSupabaseClient:
            return fake

        async def _close(client: object) -> None:
            closed.append(client)

        monkeypatch.setattr(main_module, "create_supabase_client", _create)
        monkeypatch.setattr(main_module, "close_supabase_client", _close)
        app = create_app(settings)

        async with app.router.lifespan_context(app):
            assert app.state.supabase is fake

        assert closed == [fake]
        assert app.state.supabase is None


class TestDependencyWiring:
    async def test_missing_client_is_a_domain_error(self, settings: Settings) -> None:
        """Un cliente sin inicializar no debe fallar como ``AttributeError``."""
        from app.api.deps import get_supabase_client
        from app.core.exceptions import SupabaseError

        app = create_app(settings)
        app.state.supabase = None

        class FakeRequest:
            def __init__(self, application: FastAPI) -> None:
                self.app = application

        with pytest.raises(SupabaseError):
            get_supabase_client(FakeRequest(app))  # type: ignore[arg-type]

    async def test_principal_placeholder_is_a_service_identity(self) -> None:
        """RNF-1.6: el hueco para JWT existe y las rutas ya lo pueden declarar."""
        from app.api.deps import get_current_principal

        principal = await get_current_principal()

        assert principal.is_service is True
        assert principal.subject
