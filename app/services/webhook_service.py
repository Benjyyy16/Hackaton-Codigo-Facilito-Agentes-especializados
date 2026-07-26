"""Ingesta de eventos de Jira.

Orquesta normalización, deduplicación y persistencia. No conoce HTTP ni el cliente de
Supabase: recibe repositorios y devuelve un resultado de dominio.

El orden importa: el evento se persiste **antes** de analizarlo. Si el análisis falla, el
evento sigue registrado y el fallo queda en el log; al revés se perdería información
(RF-5.8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.exceptions import DuplicateEventError
from app.core.logging import get_logger
from app.integrations.jira.normalizer import normalize_webhook_payload
from app.repositories.jira_events import JiraEventRepository
from app.repositories.projects import ProjectRepository
from app.schemas.jira import NormalizedEvent

logger = get_logger("webhook")


@dataclass(frozen=True)
class IngestOutcome:
    """Resultado de intentar ingerir un evento."""

    event: NormalizedEvent
    #: Fila persistida, o la existente si era duplicado.
    row: dict[str, Any] | None
    duplicated: bool

    @property
    def event_id(self) -> UUID | None:
        if not self.row:
            return None
        raw = self.row.get("id")
        return UUID(str(raw)) if raw else None

    @property
    def project_id(self) -> UUID | None:
        if not self.row:
            return None
        raw = self.row.get("project_id")
        return UUID(str(raw)) if raw else None


class WebhookService:
    """Convierte payloads de Jira en eventos persistidos."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        event_repository: JiraEventRepository,
    ) -> None:
        self._projects = project_repository
        self._events = event_repository

    async def ingest_payload(self, payload: dict[str, Any]) -> IngestOutcome:
        """Normaliza, deduplica y persiste un payload de webhook.

        Eleva ``UnsupportedEventError`` si el tipo no está soportado, que la ruta traduce a
        ``202`` (RF-5.4).
        """
        event = normalize_webhook_payload(payload)
        return await self.ingest_event(event)

    async def ingest_event(self, event: NormalizedEvent) -> IngestOutcome:
        """Persiste un evento ya normalizado, descartando duplicados.

        La deduplicación tiene dos capas. La comprobación previa evita la escritura en el caso
        habitual; la restricción de unicidad de la tabla cubre la condición de carrera entre
        dos entregas simultáneas del mismo evento, que la comprobación previa no puede ver
        (RF-6.2, RF-6.3, RF-6.4).
        """
        existing = await self._events.get_by_fingerprint(event.fingerprint)
        if existing is not None:
            logger.info(
                "Evento duplicado descartado: %s %s",
                event.jira_issue_key,
                event.event_type.value,
            )
            return IngestOutcome(event=event, row=existing, duplicated=True)

        project = await self._projects.ensure(
            jira_project_key=event.project_key, name=event.project_key
        )
        row_payload = event.to_row(project_id=str(project["id"]))

        try:
            row = await self._events.create(row_payload)
        except DuplicateEventError:
            # Otra entrega ganó la carrera entre la comprobación previa y esta inserción.
            logger.info(
                "Inserción duplicada resuelta por la restricción de unicidad: %s",
                event.jira_issue_key,
            )
            row = await self._events.get_by_fingerprint(event.fingerprint)
            return IngestOutcome(event=event, row=row, duplicated=True)

        logger.info(
            "Evento registrado: %s %s (id=%s)",
            event.jira_issue_key,
            event.event_type.value,
            row.get("id"),
        )
        return IngestOutcome(event=event, row=row, duplicated=False)
