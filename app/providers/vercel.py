"""Provider de Vercel.

Fuente de eventos: estado de despliegues y previews.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping
from datetime import datetime, timezone
from typing import Any, ClassVar, Final

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.providers.base import EventSink, IngestDecision
from app.schemas.common import DependencyStatus
from app.schemas.events import EventKind, ExternalEvent, ProviderName
from app.schemas.providers import (
    ProviderCapability,
    ProviderHealth,
    ProviderKind,
    SyncReport,
    SyncRequest,
)

logger = get_logger("provider.vercel")

VERCEL_API: Final[str] = "https://api.vercel.com"

#: Estado de Vercel → EventKind del dominio
DEPLOY_STATE_MAP: Final[dict[str, EventKind]] = {
    "READY":   EventKind.DEPLOYMENT_STATE_CHANGED,
    "ERROR":   EventKind.DEPLOYMENT_STATE_CHANGED,
    "BUILDING": EventKind.DEPLOYMENT_STATE_CHANGED,
    "CANCELED": EventKind.DEPLOYMENT_STATE_CHANGED,
}


class VercelProvider:
    """Vercel como fuente de eventos de despliegue."""

    name: ClassVar[ProviderName] = ProviderName.VERCEL
    kind: ClassVar[ProviderKind] = ProviderKind.EVENT_SOURCE
    capabilities: ClassVar[frozenset[ProviderCapability]] = frozenset({
        ProviderCapability.SYNC,
        ProviderCapability.WEBHOOK,
    })

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        if self._http is not None:
            return
        token = self._settings.VERCEL_TOKEN
        params = {}
        if self._settings.VERCEL_TEAM_ID:
            params["teamId"] = self._settings.VERCEL_TEAM_ID
        self._http = httpx.AsyncClient(
            base_url=VERCEL_API,
            headers={"Authorization": f"Bearer {token.get_secret_value()}"},
            params=params,
            timeout=10.0,
        )
        logger.info("Provider de Vercel conectado")

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
        self._http = None

    async def health(self) -> ProviderHealth:
        if self._http is None:
            return ProviderHealth(provider=self.name.value, status=DependencyStatus.UNKNOWN)
        started = time.perf_counter()
        try:
            r = await self._http.get("/v2/user", timeout=3.0)
            r.raise_for_status()
            status = DependencyStatus.UP
            detail = None
        except Exception as e:
            status = DependencyStatus.DOWN
            detail = type(e).__name__
        return ProviderHealth(
            provider=self.name.value,
            status=status,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            detail=detail,
        )

    def verify_webhook(self, headers: Mapping[str, str], params: Mapping[str, str]) -> None:
        pass  # Vercel webhooks usan JWT, implementar si se necesita

    def parse_webhook(self, payload: Mapping[str, Any]) -> ExternalEvent:
        """Parsea un webhook de Vercel (deployment.created, etc.)."""
        deploy = payload.get("deployment", payload)
        created_at = deploy.get("createdAt", 0)
        occurred_at = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc) if created_at else datetime.now(timezone.utc)
        project = deploy.get("name", "unknown")
        return ExternalEvent(
            provider=ProviderName.VERCEL,
            workspace_key=project,
            external_id=deploy.get("id", "unknown"),
            external_key=f"{project}@{deploy.get('id','')[:8]}",
            kind=EventKind.DEPLOYMENT_STATE_CHANGED,
            occurred_at=occurred_at,
            title=f"Deploy {deploy.get('state','?')} — {project}",
            state=deploy.get("state"),
            url=deploy.get("url"),
            raw_payload=dict(payload),
        )

    async def fetch_events(self, request: SyncRequest) -> AsyncIterator[ExternalEvent]:
        if self._http is None:
            return

        params: dict[str, Any] = {"limit": 50}
        if request.workspace_key:
            params["projectId"] = request.workspace_key

        r = await self._http.get("/v6/deployments", params=params)
        if r.status_code != 200:
            logger.warning("Vercel deployments error: %s", r.status_code)
            return

        data = r.json()
        for deploy in data.get("deployments", []):
            created_at = deploy.get("createdAt", 0)
            occurred_at = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc) if created_at else datetime.now(timezone.utc)
            project = deploy.get("name", request.workspace_key or "unknown")
            yield ExternalEvent(
                provider=ProviderName.VERCEL,
                workspace_key=project,
                external_id=deploy.get("uid", deploy.get("id", "unknown")),
                external_key=f"{project}@{deploy.get('uid','')[:8]}",
                kind=EventKind.DEPLOYMENT_STATE_CHANGED,
                occurred_at=occurred_at,
                title=f"Deploy {deploy.get('state','?')} — {project}",
                state=deploy.get("state"),
                url=f"https://{deploy.get('url')}" if deploy.get("url") else None,
                raw_payload=deploy,
            )

    async def sync(self, request: SyncRequest, sink: EventSink) -> SyncReport:
        processed = created = skipped = failed = 0
        async for event in self.fetch_events(request):
            processed += 1
            try:
                decision = await sink(event)
                if decision is IngestDecision.CREATED:
                    created += 1
                elif decision is IngestDecision.DUPLICATE:
                    skipped += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                logger.warning("Vercel sync error: %s", e)

        return SyncReport(
            provider=self.name,
            workspace_key=request.workspace_key,
            processed=processed, created=created, skipped=skipped, failed=failed,
        )
