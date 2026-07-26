"""Ingesta de eventos externos.

Normaliza, deduplica y persiste. Es el sumidero que los providers usan durante una
sincronización y el que la ruta de webhook invoca por cada entrega.

No conoce ningún provider concreto: recibe ``ExternalEvent``. Sustituye al antiguo
``webhook_service``, que hablaba el vocabulario de Jira.

El orden importa: el evento se persiste **antes** de analizarlo. Si el análisis falla, el evento
sigue registrado y el fallo queda en el log; al revés se perdería información (RF-5.8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.exceptions import DuplicateEventError
from app.core.logging import get_logger
from app.providers.base import IngestDecision
from app.repositories.events import EventRepository
from app.repositories.workspaces import WorkspaceRepository
from app.schemas.events import ExternalEvent

logger = get_logger("ingest")


@dataclass(frozen=True)
class IngestOutcome:
    """Resultado de intentar ingerir un evento."""

    event: ExternalEvent
    #: Fila persistida, o la existente si era duplicado.
    row: dict[str, Any] | None
    duplicated: bool

    @property
    def event_id(self) -> UUID | None:
        return self._uuid("id")

    @property
    def workspace_id(self) -> UUID | None:
        return self._uuid("workspace_id")

    @property
    def decision(self) -> IngestDecision:
        """Traduce el resultado al vocabulario que espera el sumidero del provider."""
        if self.duplicated:
            return IngestDecision.DUPLICATE
        return IngestDecision.CREATED if self.row else IngestDecision.FAILED

    def _uuid(self, key: str) -> UUID | None:
        if not self.row:
            return None
        raw = self.row.get(key)
        return UUID(str(raw)) if raw else None


class IngestService:
    """Convierte eventos del dominio en filas persistidas."""

    def __init__(
        self,
        workspaces: WorkspaceRepository,
        events: EventRepository,
    ) -> None:
        self._workspaces = workspaces
        self._events = events

    async def ingest(self, event: ExternalEvent) -> IngestOutcome:
        """Persiste un evento, descartando duplicados.

        La deduplicación tiene dos capas. La comprobación previa evita la escritura en el caso
        habitual; la restricción de unicidad de la tabla cubre la condición de carrera entre dos
        entregas simultáneas del mismo evento, que la comprobación previa no puede ver (RF-6.2,
        RF-6.3, RF-6.4).
        """
        existing = await self._events.get_by_fingerprint(event.fingerprint)
        if existing is not None:
            logger.info(
                "Evento duplicado descartado: %s %s %s",
                event.provider.value,
                event.external_key,
                event.kind.value,
            )
            return IngestOutcome(event=event, row=existing, duplicated=True)

        workspace = await self._workspaces.ensure(
            provider=event.provider,
            workspace_key=event.workspace_key,
            name=event.workspace_key,
        )
        row_payload = event.to_row(workspace_id=str(workspace["id"]))

        try:
            row = await self._events.create(row_payload)
        except DuplicateEventError:
            # Otra entrega ganó la carrera entre la comprobación previa y esta inserción.
            logger.info(
                "Inserción duplicada resuelta por la restricción de unicidad: %s",
                event.external_key,
            )
            row = await self._events.get_by_fingerprint(event.fingerprint)
            return IngestOutcome(event=event, row=row, duplicated=True)

        logger.info(
            "Evento registrado: %s %s %s (id=%s)",
            event.provider.value,
            event.external_key,
            event.kind.value,
            row.get("id"),
        )
        return IngestOutcome(event=event, row=row, duplicated=False)

    async def sink(self, event: ExternalEvent) -> IngestDecision:
        """Adaptador al sumidero que los providers invocan durante ``sync()``.

        Devuelve solo la decisión porque es lo único que el provider necesita para contar; el
        resto del resultado no le incumbe.
        """
        outcome = await self.ingest(event)
        return outcome.decision
