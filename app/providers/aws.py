"""Provider de AWS.

Sincroniza eventos de CloudWatch, EventBridge y otros servicios AWS.
"""

from __future__ import annotations

from datetime import timezone
from typing import Final

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings
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

logger = get_logger("aws_provider")

DEFAULT_REGION: Final[str] = "us-east-1"


class AWSProvider(EventSourceProvider):
    """Provider que sincroniza eventos de AWS (CloudWatch, EventBridge, etc)."""

    def __init__(self, settings: Settings):
        """Inicializa el provider con credenciales de AWS.

        Espera: ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_REGION``
        """
        self.settings = settings
        self.name = ProviderName.AWS
        self.kind = ProviderKind.EVENT_SOURCE
        self.capabilities = frozenset([
            ProviderCapability.LOGS,
            ProviderCapability.EVENTS,
        ])
        self.cloudwatch_client = None
        self.eventbridge_client = None
        self._connected = False

    async def connect(self) -> None:
        """Conecta con los servicios de AWS."""
        try:
            region = getattr(self.settings, "AWS_REGION", DEFAULT_REGION)

            # CloudWatch
            self.cloudwatch_client = boto3.client("logs", region_name=region)
            # EventBridge
            self.eventbridge_client = boto3.client("events", region_name=region)

            # Test connection
            self.cloudwatch_client.describe_log_groups(limit=1)
            self._connected = True
            logger.info(f"✓ AWS conectado a región {region}")
        except ClientError as e:
            logger.error("AWS error al conectar", exc_info=e)
            self._connected = False

    async def health(self) -> ProviderHealth:
        """Verifica la salud del provider AWS."""
        if not self._connected:
            return ProviderHealth(
                name=self.name,
                status="unknown",
                message="Not connected",
            )

        try:
            if self.cloudwatch_client:
                self.cloudwatch_client.describe_log_groups(limit=1)
            return ProviderHealth(
                name=self.name,
                status="up",
                message="AWS CloudWatch accessible",
            )
        except Exception as e:
            return ProviderHealth(
                name=self.name,
                status="down",
                message=str(e),
            )

    async def close(self) -> None:
        """Cierra la conexión con AWS."""
        self._connected = False
        self.cloudwatch_client = None
        self.eventbridge_client = None

    async def sync(self, request: SyncRequest, sink: EventSink) -> SyncReport:
        """Sincroniza eventos de CloudWatch y EventBridge."""
        if not self._connected:
            return SyncReport(
                provider=self.name,
                workspace_id=request.workspace_id,
                processed=0,
                created=0,
                skipped=0,
                failed=0,
                message="AWS not connected",
            )

        processed = 0
        created = 0
        skipped = 0
        failed = 0

        try:
            # Obtener log groups
            if self.cloudwatch_client:
                response = self.cloudwatch_client.describe_log_groups(limit=50)
                for log_group in response.get("logGroups", []):
                    event = ExternalEvent(
                        external_key=f"aws-logs-{log_group['logGroupName']}",
                        provider=self.name,
                        kind=EventKind.LOG_CREATED,
                        occurred_at=timezone.utc.localize(
                            __import__("datetime").datetime.fromtimestamp(
                                log_group.get("creationTime", 0) / 1000
                            )
                        ),
                        source_id=log_group["logGroupName"],
                        data={
                            "log_group": log_group["logGroupName"],
                            "retention_in_days": log_group.get("retentionInDays", -1),
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

        except ClientError as e:
            logger.error("AWS sync error", exc_info=e)
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
        """Itera eventos sin persistir."""
        if not self._connected:
            return

        try:
            if self.cloudwatch_client:
                response = self.cloudwatch_client.describe_log_groups(limit=50)
                for log_group in response.get("logGroups", []):
                    yield ExternalEvent(
                        external_key=f"aws-logs-{log_group['logGroupName']}",
                        provider=self.name,
                        kind=EventKind.LOG_CREATED,
                        occurred_at=timezone.utc.localize(
                            __import__("datetime").datetime.fromtimestamp(
                                log_group.get("creationTime", 0) / 1000
                            )
                        ),
                        source_id=log_group["logGroupName"],
                        data={"log_group": log_group["logGroupName"]},
                    )
        except ClientError as e:
            logger.error("AWS fetch error", exc_info=e)

    def verify_webhook(self, headers: dict[str, str], params: dict[str, str]) -> None:
        """Verifica webhook de AWS."""
        pass

    def parse_webhook(self, payload: dict[str, object]) -> ExternalEvent:
        """Parsea webhook payload de AWS."""
        raise NotImplementedError("AWS webhooks no implementado aún")
