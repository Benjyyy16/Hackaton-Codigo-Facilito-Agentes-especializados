"""Provider de GitHub.

Sincroniza issues, pull requests y eventos de repositorios.
"""

from __future__ import annotations

from datetime import timezone
from typing import Final

import httpx
from github import Github, GithubException

from app.core.config import Settings
from app.core.exceptions import IntegrationError
from app.core.logging import get_logger
from app.providers.base import EventSink, EventSourceProvider, IngestDecision
from app.schemas.events import EventKind, ExternalEvent, ProviderName
from app.schemas.providers import (
    ProviderCapability,
    ProviderHealth,
    ProviderKind,
    SyncReport,
    SyncRequest,
)

logger = get_logger("github_provider")

GITHUB_API_BASE: Final[str] = "https://api.github.com"
DEFAULT_ISSUE_FIELDS: Final[list[str]] = ["id", "number", "title", "state", "created_at", "updated_at"]


class GitHubProvider(EventSourceProvider):
    """Provider que sincroniza eventos de repositorios GitHub."""

    def __init__(self, settings: Settings):
        """Inicializa el provider con credenciales de GitHub.

        Espera: ``GITHUB_TOKEN`` (token personal o app)
        """
        self.settings = settings
        self.name = ProviderName.GITHUB
        self.kind = ProviderKind.EVENT_SOURCE
        self.capabilities = frozenset([
            ProviderCapability.ISSUES,
            ProviderCapability.PULL_REQUESTS,
            ProviderCapability.COMMENTS,
        ])
        self.client = None
        self._connected = False

    async def connect(self) -> None:
        """Conecta con la API de GitHub."""
        try:
            token = self.settings.__dict__.get("GITHUB_TOKEN", "")
            if not token:
                logger.warning("GITHUB_TOKEN no configurado, GitHub desactivado")
                return

            # GitHub client es síncrono pero lo importamos aquí
            self.client = Github(token)
            # Test connection
            self.client.get_user().login
            self._connected = True
            logger.info("✓ GitHub conectado")
        except GithubException as e:
            logger.error("GitHub error al conectar", exc_info=e)
            self._connected = False

    async def health(self) -> ProviderHealth:
        """Verifica la salud del provider GitHub."""
        if not self._connected:
            return ProviderHealth(
                name=self.name,
                status="unknown",
                message="Not connected",
            )

        try:
            if self.client:
                self.client.get_user().login
            return ProviderHealth(
                name=self.name,
                status="up",
                message="GitHub API accessible",
            )
        except Exception as e:
            return ProviderHealth(
                name=self.name,
                status="down",
                message=str(e),
            )

    async def close(self) -> None:
        """Cierra la conexión con GitHub."""
        self._connected = False
        self.client = None

    async def sync(self, request: SyncRequest, sink: EventSink) -> SyncReport:
        """Sincroniza issues de los repositorios solicitados."""
        if not self._connected or not self.client:
            return SyncReport(
                provider=self.name,
                workspace_id=request.workspace_id,
                processed=0,
                created=0,
                skipped=0,
                failed=0,
                message="GitHub not connected",
            )

        processed = 0
        created = 0
        skipped = 0
        failed = 0

        try:
            # Para este demo, iteramos repos públicos del usuario
            user = self.client.get_user()
            for repo in user.get_repos(type="owner"):
                # Obtener issues abiertos
                for issue in repo.get_issues(state="open"):
                    event = ExternalEvent(
                        external_key=f"github-{repo.name}-{issue.number}",
                        provider=self.name,
                        kind=EventKind.ISSUE_CREATED if issue.state == "open" else EventKind.ISSUE_UPDATED,
                        occurred_at=issue.updated_at.replace(tzinfo=timezone.utc),
                        source_id=repo.name,
                        data={
                            "issue_number": issue.number,
                            "title": issue.title,
                            "state": issue.state,
                            "author": issue.user.login if issue.user else "unknown",
                        },
                    )

                    processed += 1
                    decision = await sink(event)
                    if decision == IngestDecision.CREATED:
                        created += 1
                    elif decision == IngestDecision.DUPLICATE:
                        skipped += 1
                    elif decision == IngestDecision.FAILED:
                        failed += 1

        except GithubException as e:
            logger.error("GitHub sync error", exc_info=e)
            failed += 1

        return SyncReport(
            provider=self.name,
            workspace_id=request.workspace_id,
            processed=processed,
            created=created,
            skipped=skipped,
            failed=failed,
        )

    async def fetch_events(self, request: SyncRequest):
        """Itera issues sin persistir."""
        if not self._connected or not self.client:
            return

        try:
            user = self.client.get_user()
            for repo in user.get_repos(type="owner"):
                for issue in repo.get_issues(state="open"):
                    yield ExternalEvent(
                        external_key=f"github-{repo.name}-{issue.number}",
                        provider=self.name,
                        kind=EventKind.ISSUE_CREATED,
                        occurred_at=issue.updated_at.replace(tzinfo=timezone.utc),
                        source_id=repo.name,
                        data={
                            "issue_number": issue.number,
                            "title": issue.title,
                        },
                    )
        except GithubException as e:
            logger.error("GitHub fetch error", exc_info=e)

    def verify_webhook(self, headers: dict[str, str], params: dict[str, str]) -> None:
        """Verifica webhook de GitHub."""
        # Implementar verificación con HMAC SHA-256
        # Por ahora, permitir todos
        pass

    def parse_webhook(self, payload: dict[str, object]) -> ExternalEvent:
        """Parsea webhook payload."""
        # Implementar parsing de webhook
        raise NotImplementedError("GitHub webhooks no implementado aún")
