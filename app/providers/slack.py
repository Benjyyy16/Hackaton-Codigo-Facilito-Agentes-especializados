"""Provider de Slack.

Slack no es una fuente de eventos del dominio (issues, PRs), sino un canal de notificaciones.
Este provider implementa el puerto mínimo para registrarse y reportar salud,
y expone un método ``notify`` para enviar alertas.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping
from typing import Any, ClassVar

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.base import EventSink
from app.schemas.common import DependencyStatus
from app.schemas.events import ExternalEvent, ProviderName
from app.schemas.providers import (
    ProviderCapability,
    ProviderHealth,
    ProviderKind,
    SyncReport,
    SyncRequest,
)

logger = get_logger("provider.slack")


class SlackProvider:
    """Slack como canal de notificaciones."""

    name: ClassVar[ProviderName] = ProviderName.SLACK
    kind: ClassVar[ProviderKind] = ProviderKind.NOTIFICATION
    capabilities: ClassVar[frozenset[ProviderCapability]] = frozenset({
        ProviderCapability.NOTIFY,
    })

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        if self._http is not None:
            return
        token = self._settings.SLACK_BOT_TOKEN
        self._http = httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={"Authorization": f"Bearer {token.get_secret_value()}"},
            timeout=10.0,
        )
        logger.info("Provider de Slack conectado")

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
        self._http = None

    async def health(self) -> ProviderHealth:
        if self._http is None:
            return ProviderHealth(provider=self.name.value, status=DependencyStatus.UNKNOWN)
        started = time.perf_counter()
        try:
            r = await self._http.post("/auth.test", timeout=3.0)
            data = r.json()
            if data.get("ok"):
                status = DependencyStatus.UP
                detail = f"team={data.get('team')}"
            else:
                status = DependencyStatus.DOWN
                detail = data.get("error", "unknown")
        except Exception as e:
            status = DependencyStatus.DOWN
            detail = type(e).__name__
        return ProviderHealth(
            provider=self.name.value,
            status=status,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            detail=detail,
        )

    async def notify(self, message: str, *, channel: str | None = None) -> bool:
        """Envía un mensaje al canal configurado. Devuelve True si tuvo éxito."""
        if self._http is None:
            return False
        ch = channel or self._settings.SLACK_CHANNEL or "#alerts"
        try:
            r = await self._http.post(
                "/chat.postMessage",
                json={"channel": ch, "text": message},
            )
            data = r.json()
            if not data.get("ok"):
                logger.warning("Slack error: %s", data.get("error"))
            return bool(data.get("ok"))
        except Exception as e:
            logger.error("Slack notify error: %s", e)
            return False

    def verify_webhook(self, headers: Mapping[str, str], params: Mapping[str, str]) -> None:
        pass

    def parse_webhook(self, payload: Mapping[str, Any]) -> ExternalEvent:
        raise NotImplementedError("Slack no produce eventos del dominio")

    async def fetch_events(self, request: SyncRequest) -> AsyncIterator[ExternalEvent]:
        return  # type: ignore[return-value]
        yield  # noqa: unreachable

    async def sync(self, request: SyncRequest, sink: EventSink) -> SyncReport:
        return SyncReport(
            provider=self.name,
            workspace_key=request.workspace_key,
            processed=0, created=0, skipped=0, failed=0,
            message="Slack es solo notificaciones, sin sincronización.",
        )
