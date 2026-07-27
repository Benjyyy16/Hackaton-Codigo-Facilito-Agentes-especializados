"""Difusión de eventos por WebSocket.

El gestor mantiene el conjunto de conexiones activas protegido por un ``asyncio.Lock``,
porque conexiones y desconexiones concurrentes mutan el conjunto y hacerlo sin cerrojo
produce un ``RuntimeError`` durante la iteración de difusión.

``broadcast`` envía a cada cliente dentro de su propio ``try`` y recoge los que fallan
para retirarlos después. Un socket muerto no debe impedir la entrega al resto, y
retirarlo durante la iteración mutaría el conjunto que se está recorriendo.

Sin clientes conectados, difundir no es un error: simplemente no hay a quién enviar.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

from fastapi import WebSocket
from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StrEnum
from app.core.logging import get_logger

logger = get_logger("websocket")

#: Versión del sobre de mensajes. Viaja en cada evento para que un cliente antiguo
#: pueda detectar que el formato cambió en lugar de fallar al interpretar campos nuevos.
EVENT_VERSION: Final[str] = "1.0"


class EventType(StrEnum):
    """Tipos de evento que el backend difunde.

    El tipo declarado permite al consumidor discriminar sin inspeccionar la forma de la
    carga. Es un enum cerrado porque el frontend enruta por él: admitir cadenas libres
    significaría que un typo en el backend se manifiesta como un evento silenciosamente
    ignorado.
    """

    SOURCE_EVENT_RECEIVED = "source_event.received"
    ANALYSIS_STARTED = "analysis.started"
    AGENT_RUN_STARTED = "agent_run.started"
    AGENT_RUN_COMPLETED = "agent_run.completed"
    RISK_CASE_CREATED = "risk_case.created"
    RISK_CASE_UPDATED = "risk_case.updated"
    ALERT_CREATED = "alert.created"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"
    EVIDENCE_CREATED = "evidence.created"
    DECISION_CREATED = "decision.created"
    DECISION_APPROVED = "decision.approved"
    DECISION_REJECTED = "decision.rejected"
    DECISION_EXECUTED = "decision.executed"
    DECISION_UPDATED = "decision.updated"
    COMMITMENT_STATUS_CHANGED = "commitment.status_changed"
    TIMELINE_APPENDED = "timeline.appended"
    ANALYSIS_COMPLETED = "analysis.completed"


class WsEvent(BaseModel):
    """Sobre estándar de los mensajes de WebSocket.

    Los identificadores viajan en el sobre y no dentro de ``data`` a propósito: un
    cliente puede filtrar por compromiso sin conocer la forma de la carga de cada tipo
    de evento.
    """

    model_config = ConfigDict(frozen=True)

    type: EventType
    version: str = EVENT_VERSION
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    project_id: UUID | None = None
    commitment_id: UUID | None = None
    risk_case_id: UUID | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ConnectionManager:
    """Conjunto de conexiones activas, con difusión tolerante a fallos."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Acepta la conexión y la registra."""
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("Cliente WebSocket conectado (total: %d)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Retira la conexión.

        ``discard`` y no ``remove``: desconectar dos veces es normal (el cliente cierra y
        el servidor detecta el cierre), y elevar por ello obligaría a cada llamador a
        envolver la llamada en un ``try``.
        """
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("Cliente WebSocket desconectado (total: %d)", len(self._connections))

    async def broadcast(self, event: WsEvent) -> int:
        """Difunde un evento a todos los clientes. Devuelve cuántos lo recibieron.

        Se toma una instantánea del conjunto bajo cerrojo y se envía fuera de él: enviar
        con el cerrojo tomado bloquearía las conexiones nuevas durante toda la difusión,
        y un cliente lento arrastraría a los demás.
        """
        async with self._lock:
            targets = list(self._connections)

        if not targets:
            return 0

        payload = event.model_dump(mode="json")
        broken: list[WebSocket] = []
        delivered = 0

        for websocket in targets:
            try:
                await websocket.send_json(payload)
                delivered += 1
            except Exception as error:  # noqa: BLE001 - un socket roto no detiene al resto
                logger.warning(
                    "Fallo al enviar a un cliente WebSocket: %s", type(error).__name__
                )
                broken.append(websocket)

        if broken:
            async with self._lock:
                for websocket in broken:
                    self._connections.discard(websocket)

        return delivered

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    def __len__(self) -> int:
        return len(self._connections)
