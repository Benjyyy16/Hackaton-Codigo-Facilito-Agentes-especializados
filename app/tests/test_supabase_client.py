"""Tests del ciclo de vida del cliente de Supabase."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.exceptions import SupabaseError
from app.integrations.supabase import client as supabase_client
from app.tests.conftest import VALID_SETTINGS
from app.tests.fakes.supabase import FakeSupabaseClient


class TestClientCreation:
    async def test_library_failure_is_translated(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ninguna capa superior debe conocer las excepciones de la librería."""

        async def _fail(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("handshake fallido")

        monkeypatch.setattr(supabase_client, "acreate_client", _fail)

        with pytest.raises(SupabaseError):
            await supabase_client.create_supabase_client(settings)

    async def test_failure_message_does_not_leak_the_key(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = VALID_SETTINGS["SUPABASE_SERVICE_ROLE_KEY"]

        async def _fail(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError(f"clave rechazada: {secret}")

        monkeypatch.setattr(supabase_client, "acreate_client", _fail)

        with pytest.raises(SupabaseError) as excinfo:
            await supabase_client.create_supabase_client(settings)

        assert secret not in str(excinfo.value)

    async def test_service_role_key_is_used(
        self, settings: Settings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """El backend escribe como servicio de confianza, no con la clave anónima."""
        seen: dict[str, object] = {}

        async def _capture(url: str, key: str, *_a: object, **_kw: object) -> object:
            seen["url"] = url
            seen["key"] = key
            return FakeSupabaseClient()

        monkeypatch.setattr(supabase_client, "acreate_client", _capture)

        await supabase_client.create_supabase_client(settings)

        assert seen["url"] == settings.SUPABASE_URL
        assert seen["key"] == settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()


class TestPing:
    """RF-2.3: la sonda informa del estado, no falla."""

    async def test_reachable_backend_returns_true(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("projects").returns([])

        assert await supabase_client.ping(fake) is True

    async def test_unreachable_backend_returns_false(self) -> None:
        fake = FakeSupabaseClient()
        fake.for_table("projects").raises(ConnectionError("sin ruta al host"))

        assert await supabase_client.ping(fake) is False

    async def test_probe_does_not_pull_data(self) -> None:
        """Interesa saber si PostgREST responde, no traer filas."""
        fake = FakeSupabaseClient()
        fake.for_table("projects").returns([])

        await supabase_client.ping(fake)

        assert fake.for_table("projects").calls_to("limit")[0].args == (1,)


class TestShutdown:
    async def test_closing_none_is_a_no_op(self) -> None:
        await supabase_client.close_supabase_client(None)

    async def test_client_without_close_method_is_tolerated(self) -> None:
        """La versión instalada de supabase-py no expone cierre explícito."""
        await supabase_client.close_supabase_client(FakeSupabaseClient())

    async def test_failure_while_closing_does_not_propagate(self) -> None:
        """El apagado no es lugar para fallar."""

        class Failing:
            async def aclose(self) -> None:
                raise RuntimeError("socket ya cerrado")

        await supabase_client.close_supabase_client(Failing())
