"""Provider de Notion.

Fuente de eventos: páginas y bases de datos de Notion.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping
from datetime import datetime
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

logger = get_logger("provider.notion")

NOTION_API: Final[str] = "https://api.notion.com/v1"
NOTION_VERSION: Final[str] = "2022-06-28"


class NotionProvider:
    """Notion como fuente de eventos."""

    name: ClassVar[ProviderName] = ProviderName.NOTION
    kind: ClassVar[ProviderKind] = ProviderKind.EVENT_SOURCE
    capabilities: ClassVar[frozenset[ProviderCapability]] = frozenset({
        ProviderCapability.SYNC,
    })

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        if self._http is not None:
            return
        token = self._settings.NOTION_TOKEN
        self._http = httpx.AsyncClient(
            base_url=NOTION_API,
            headers={
                "Authorization": f"Bearer {token.get_secret_value()}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        logger.info("Provider de Notion conectado")

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
        self._http = None

    async def health(self) -> ProviderHealth:
        if self._http is None:
            return ProviderHealth(provider=self.name.value, status=DependencyStatus.UNKNOWN)
        started = time.perf_counter()
        try:
            r = await self._http.get("/users/me", timeout=3.0)
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
        pass  # Notion no tiene webhooks con firma

    def parse_webhook(self, payload: Mapping[str, Any]) -> ExternalEvent:
        raise NotImplementedError("Webhooks de Notion no implementados")

    async def fetch_events(self, request: SyncRequest) -> AsyncIterator[ExternalEvent]:
        if self._http is None:
            return

        db_id = request.workspace_key or self._settings.NOTION_DATABASE_ID
        if not db_id:
            return

        cursor = None
        while True:
            body: dict[str, Any] = {"page_size": 100, "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}]}
            if cursor:
                body["start_cursor"] = cursor

            r = await self._http.post(f"/databases/{db_id}/query", json=body)
            if r.status_code != 200:
                logger.warning("Notion query falló: %s", r.status_code)
                break

            data = r.json()
            for page in data.get("results", []):
                props = page.get("properties", {})
                title_prop = next(
                    (v for v in props.values() if v.get("type") == "title"),
                    {}
                )
                title = "".join(
                    t.get("plain_text", "")
                    for t in title_prop.get("title", [])
                )
                last_edited = page.get("last_edited_time", "")
                created_time = page.get("created_time", "")

                occurred_at = datetime.fromisoformat(
                    (last_edited or created_time).replace("Z", "+00:00")
                )
                is_new = last_edited == created_time

                yield ExternalEvent(
                    provider=ProviderName.NOTION,
                    workspace_key=db_id,
                    external_id=page["id"],
                    external_key=page["id"][:8],
                    kind=EventKind.WORK_ITEM_CREATED if is_new else EventKind.WORK_ITEM_UPDATED,
                    occurred_at=occurred_at,
                    title=title or None,
                    url=page.get("url"),
                    raw_payload=page,
                )

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

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
                logger.warning("Notion sync error: %s", e)

        return SyncReport(
            provider=self.name,
            workspace_key=request.workspace_key,
            processed=processed, created=created, skipped=skipped, failed=failed,
        )
