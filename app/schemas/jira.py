"""Schemas de Jira: payload de webhook y evento normalizado.

El resto del sistema solo conoce ``NormalizedEvent``. Un cambio de forma en la API o en el
webhook de Jira se absorbe en el normalizador, no se propaga.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

#: Tipos de evento del webhook de Jira que este backend acepta (RF-5.3).
JIRA_WEBHOOK_ISSUE_CREATED: Final[str] = "jira:issue_created"
JIRA_WEBHOOK_ISSUE_UPDATED: Final[str] = "jira:issue_updated"
JIRA_WEBHOOK_COMMENT_CREATED: Final[str] = "comment_created"


class EventType(StrEnum):
    """Tipo de evento en el modelo interno.

    Los valores coinciden con la restricción ``check`` de ``jira_events.event_type``.
    """

    ISSUE_CREATED = "issue_created"
    ISSUE_UPDATED = "issue_updated"
    COMMENT_CREATED = "comment_created"


#: Correspondencia entre el evento del webhook y el tipo interno. Lo que no está aquí se
#: descarta de forma explícita (RF-5.4).
WEBHOOK_EVENT_MAP: Final[dict[str, EventType]] = {
    JIRA_WEBHOOK_ISSUE_CREATED: EventType.ISSUE_CREATED,
    JIRA_WEBHOOK_ISSUE_UPDATED: EventType.ISSUE_UPDATED,
    JIRA_WEBHOOK_COMMENT_CREATED: EventType.COMMENT_CREATED,
    # Jira usa este nombre en algunas configuraciones de webhook.
    "jira:comment_created": EventType.COMMENT_CREATED,
}


class ChangedField(BaseModel):
    """Un campo modificado, tal como llega en el ``changelog`` de Jira."""

    field: str = Field(description="Nombre del campo modificado.")
    from_value: str | None = Field(default=None, description="Valor anterior.")
    to_value: str | None = Field(default=None, description="Valor nuevo.")


class NormalizedEvent(BaseModel):
    """Evento de Jira traducido al modelo interno.

    Es la frontera de la integración: los agentes y los servicios trabajan con esta forma y no
    con el payload de Jira.
    """

    model_config = ConfigDict(frozen=True)

    jira_issue_id: str = Field(description="Identificador numérico del issue en Jira.")
    jira_issue_key: str = Field(description="Clave legible del issue, por ejemplo DEMO-12.")
    project_key: str = Field(description="Clave del proyecto en Jira.")
    event_type: EventType = Field(description="Tipo de evento normalizado.")
    occurred_at: datetime = Field(description="Instante del cambio, en UTC.")

    summary: str | None = Field(default=None, description="Resumen del issue.")
    status: str | None = Field(default=None, description="Estado actual del issue.")
    assignee: str | None = Field(default=None, description="Persona asignada.")
    priority: str | None = Field(default=None, description="Prioridad declarada.")
    due_date: datetime | None = Field(default=None, description="Fecha de vencimiento.")
    estimated_hours: float | None = Field(
        default=None, description="Estimación original, convertida a horas."
    )
    labels: list[str] = Field(default_factory=list, description="Etiquetas del issue.")
    changed_fields: list[ChangedField] = Field(
        default_factory=list, description="Campos modificados en este evento."
    )
    comment_body: str | None = Field(
        default=None, description="Texto del comentario, si el evento es de comentario."
    )

    raw_payload: dict[str, Any] = Field(
        description="Payload original de Jira, sin modificar (RF-5.6)."
    )

    @property
    def fingerprint(self) -> str:
        """Huella determinística para deduplicar (RF-6.1).

        El instante se normaliza a UTC antes de formatearlo, de modo que el mismo momento
        expresado en dos zonas distintas produzca la misma huella.
        """
        moment = self.occurred_at.astimezone(UTC).isoformat()
        material = f"{self.jira_issue_id}:{self.event_type.value}:{moment}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def to_row(self, *, project_id: str | None) -> dict[str, Any]:
        """Convierte el evento en la fila de ``jira_events``."""
        return {
            "project_id": project_id,
            "jira_issue_id": self.jira_issue_id,
            "jira_issue_key": self.jira_issue_key,
            "event_type": self.event_type.value,
            "fingerprint": self.fingerprint,
            "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
            "raw_payload": self.raw_payload,
        }


class JiraSyncRequest(BaseModel):
    """Cuerpo de ``POST /jira/sync``."""

    project_key: str = Field(
        min_length=1,
        max_length=64,
        description="Clave del proyecto en Jira, por ejemplo DEMO.",
    )
    jql: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "JQL propio. Si se omite, se construye a partir de la clave de proyecto."
        ),
    )
    max_issues: int | None = Field(
        default=None,
        ge=1,
        le=5000,
        description="Tope de issues a procesar. Útil para una primera carga acotada.",
    )


class JiraSyncResult(BaseModel):
    """Resultado de una sincronización (RF-4.5)."""

    project_key: str = Field(description="Proyecto sincronizado.")
    jql: str = Field(description="JQL efectivamente ejecutado.")
    processed: int = Field(description="Issues recuperados de Jira.")
    created: int = Field(description="Eventos nuevos persistidos.")
    skipped: int = Field(description="Eventos omitidos por ser duplicados.")
    failed: int = Field(default=0, description="Issues que no se pudieron procesar.")
    truncated: bool = Field(
        default=False,
        description="Indica si la recogida se detuvo por un límite de seguridad.",
    )


class WebhookAck(BaseModel):
    """Respuesta a Jira tras recibir un webhook.

    Se responde rápido y con poco cuerpo: Jira reintenta si la respuesta tarda (RF-5.1).
    """

    accepted: bool = Field(description="Indica si el evento se aceptó para procesar.")
    duplicated: bool = Field(
        default=False, description="El evento ya se había registrado (RF-5.5)."
    )
    event_id: str | None = Field(
        default=None, description="Identificador del evento persistido."
    )
    detail: str | None = Field(default=None, description="Motivo, si no se aceptó.")
