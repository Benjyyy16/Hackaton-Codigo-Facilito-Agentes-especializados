"""Provider de GitHub.

Fuente de eventos: issues, pull requests y commits de repositorios.
"""

from __future__ import annotations

import hmac
import hashlib
import time
from collections.abc import AsyncIterator, Mapping
from typing import Any, ClassVar, Final

import httpx

from app.core.config import Settings
from app.core.exceptions import UnsupportedEventError, WebhookAuthError
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

logger = get_logger("provider.github")

GITHUB_API: Final[str] = "https://api.github.com"
SIGNATURE_HEADER: Final[str] = "X-Hub-Signature-256"

#: Eventos de GitHub que producen ExternalEvent. El resto se descartan con 202.
SUPPORTED_EVENTS: Final[frozenset[str]] = frozenset({
    "issues", "pull_request", "push", "issue_comment", "pull_request_review",
})


def _map_event(payload: dict[str, Any], event_type: str) -> ExternalEvent:
    """Traduce un payload de GitHub al modelo del dominio."""
    from datetime import datetime, timezone

    action = payload.get("action", "")

    if event_type == "issues":
        issue = payload["issue"]
        kind = EventKind.WORK_ITEM_CREATED if action == "opened" else EventKind.WORK_ITEM_UPDATED
        repo = payload["repository"]["full_name"]
        return ExternalEvent(
            provider=ProviderName.GITHUB,
            workspace_key=repo,
            external_id=str(issue["id"]),
            external_key=f"{repo}#{issue['number']}",
            kind=kind,
            occurred_at=datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00")),
            title=issue.get("title"),
            state=issue.get("state"),
            owner=issue.get("assignee", {}).get("login") if issue.get("assignee") else None,
            url=issue.get("html_url"),
            raw_payload=payload,
        )

    if event_type == "pull_request":
        pr = payload["pull_request"]
        kind = EventKind.REVIEW_REQUESTED if action == "opened" else EventKind.REVIEW_COMPLETED
        repo = payload["repository"]["full_name"]
        return ExternalEvent(
            provider=ProviderName.GITHUB,
            workspace_key=repo,
            external_id=str(pr["id"]),
            external_key=f"{repo}/pr#{pr['number']}",
            kind=kind,
            occurred_at=datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00")),
            title=pr.get("title"),
            state=pr.get("state"),
            owner=pr.get("assignee", {}).get("login") if pr.get("assignee") else None,
            url=pr.get("html_url"),
            raw_payload=payload,
        )

    if event_type == "push":
        repo = payload["repository"]["full_name"]
        commit = payload.get("head_commit") or {}
        return ExternalEvent(
            provider=ProviderName.GITHUB,
            workspace_key=repo,
            external_id=payload.get("after", "unknown"),
            external_key=f"{repo}@{payload.get('after','')[:7]}",
            kind=EventKind.DEPLOYMENT_STATE_CHANGED,
            occurred_at=datetime.now(timezone.utc),
            title=commit.get("message", "")[:120],
            raw_payload=payload,
        )

    if event_type == "issue_comment":
        issue = payload["issue"]
        comment = payload.get("comment", {})
        repo = payload["repository"]["full_name"]
        return ExternalEvent(
            provider=ProviderName.GITHUB,
            workspace_key=repo,
            external_id=str(comment.get("id", issue["id"])),
            external_key=f"{repo}#{issue['number']}/comment",
            kind=EventKind.COMMENT_ADDED,
            occurred_at=datetime.fromisoformat(
                comment.get("updated_at", issue["updated_at"]).replace("Z", "+00:00")
            ),
            comment=comment.get("body"),
            url=comment.get("html_url"),
            raw_payload=payload,
        )

    raise UnsupportedEventError(f"Evento de GitHub no soportado: {event_type}/{action}")


class GitHubProvider:
    """GitHub como fuente de eventos."""

    name: ClassVar[ProviderName] = ProviderName.GITHUB
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
        token = self._settings.GITHUB_TOKEN
        self._http = httpx.AsyncClient(
            base_url=GITHUB_API,
            headers={
                "Authorization": f"Bearer {token.get_secret_value()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10.0,
        )
        logger.info("Provider de GitHub conectado")

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
        self._http = None

    async def health(self) -> ProviderHealth:
        if self._http is None:
            return ProviderHealth(provider=self.name.value, status=DependencyStatus.UNKNOWN)
        started = time.perf_counter()
        try:
            r = await self._http.get("/rate_limit", timeout=3.0)
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
        """Verifica la firma HMAC-SHA256 de GitHub (X-Hub-Signature-256)."""
        secret = self._settings.GITHUB_WEBHOOK_SECRET
        if secret is None:
            return  # sin secreto configurado, aceptar todo
        signature = headers.get(SIGNATURE_HEADER) or headers.get(SIGNATURE_HEADER.lower())
        if not signature:
            raise WebhookAuthError("Falta la cabecera X-Hub-Signature-256")
        # La firma viene como "sha256=<hex>"
        if not signature.startswith("sha256="):
            raise WebhookAuthError("Formato de firma inválido")
        expected = hmac.new(
            secret.get_secret_value().encode(),
            params.get("body", b""),  # type: ignore[arg-type]
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(f"sha256={expected}", signature):
            raise WebhookAuthError("Firma de GitHub inválida")

    def parse_webhook(self, payload: Mapping[str, Any]) -> ExternalEvent:
        event_type = payload.get("_github_event", "issues")  # header X-GitHub-Event
        return _map_event(dict(payload), event_type)

    async def fetch_events(self, request: SyncRequest) -> AsyncIterator[ExternalEvent]:
        if self._http is None:
            return
        # El repositorio llega en la petición: GITHUB_ORG solo serviría para
        # completar un nombre corto, y aquí siempre viene "owner/repo".
        repo_path = request.workspace_key  # ej: "owner/repo"

        page = 1
        while True:
            r = await self._http.get(
                f"/repos/{repo_path}/issues",
                params={"state": "all", "per_page": 50, "page": page, "sort": "updated"},
            )
            if r.status_code != 200:
                break
            issues = r.json()
            if not issues:
                break
            for issue in issues:
                from datetime import datetime
                yield ExternalEvent(
                    provider=ProviderName.GITHUB,
                    workspace_key=repo_path,
                    external_id=str(issue["id"]),
                    external_key=f"{repo_path}#{issue['number']}",
                    kind=EventKind.WORK_ITEM_CREATED if issue.get("state") == "open" else EventKind.WORK_ITEM_UPDATED,
                    occurred_at=datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00")),
                    title=issue.get("title"),
                    state=issue.get("state"),
                    url=issue.get("html_url"),
                    raw_payload=issue,
                )
            if len(issues) < 50:
                break
            page += 1

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
                logger.warning("GitHub sync error en %s: %s", event.external_key, e)

        return SyncReport(
            provider=self.name,
            workspace_key=request.workspace_key,
            processed=processed, created=created, skipped=skipped, failed=failed,
        )
