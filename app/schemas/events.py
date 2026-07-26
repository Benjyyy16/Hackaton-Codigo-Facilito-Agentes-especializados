"""Modelo de evento agnóstico del provider.

Es la frontera del dominio. Los servicios y los agentes trabajan con ``ExternalEvent`` y no
saben de qué sistema vino: un evento de Jira, uno de GitHub y uno de Notion tienen la misma
forma aquí.

El vocabulario es del dominio, no de Jira. ``EventKind.WORK_ITEM_UPDATED`` cubre un issue de
Jira, un issue de GitHub y una página de Notion; si el enum hablara de "issues", cada provider
nuevo obligaría a ampliarlo y los agentes tendrían que conocer la diferencia.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import StrEnum


class ProviderName(StrEnum):
    """Providers reconocidos.

    Es un enum cerrado a propósito: el nombre viaja en la URL del webhook y en la base de
    datos, así que admitir cadenas libres permitiría registrar eventos bajo un provider
    inventado.
    """

    JIRA = "jira"
    GITHUB = "github"
    NOTION = "notion"
    AWS = "aws"
    RIGHTWAY = "rightway"
    SLACK = "slack"
    VERCEL = "vercel"


class EventKind(StrEnum):
    """Tipo de evento en vocabulario del dominio.

    Correspondencias previstas:

    ==========================  ==============  ==================  ==============
    kind                        Jira            GitHub              Notion
    ==========================  ==============  ==================  ==============
    work_item_created           issue creado    issue abierto       página creada
    work_item_updated           issue editado   issue editado       página editada
    comment_added               comentario      comentario          comentario
    review_requested            —               PR abierto          —
    review_completed            —               PR revisado         —
    deployment_state_changed    —               despliegue          —
    ==========================  ==============  ==================  ==============
    """

    WORK_ITEM_CREATED = "work_item_created"
    WORK_ITEM_UPDATED = "work_item_updated"
    COMMENT_ADDED = "comment_added"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_COMPLETED = "review_completed"
    DEPLOYMENT_STATE_CHANGED = "deployment_state_changed"


class FieldChange(BaseModel):
    """Un campo que cambió en este evento."""

    model_config = ConfigDict(frozen=True)

    field: str = Field(description="Nombre del campo modificado.")
    from_value: str | None = Field(default=None, description="Valor anterior.")
    to_value: str | None = Field(default=None, description="Valor nuevo.")


class ExternalEvent(BaseModel):
    """Evento de un sistema externo, traducido al modelo del dominio."""

    model_config = ConfigDict(frozen=True)

    # --- Procedencia --------------------------------------------------------------
    provider: ProviderName = Field(description="Sistema de origen.")
    workspace_key: str = Field(
        description="Contenedor en el origen: proyecto de Jira, repositorio, base de Notion."
    )
    external_id: str = Field(description="Identificador en el sistema de origen.")
    external_key: str = Field(
        description="Referencia legible: DEMO-42, owner/repo#17."
    )

    # --- Qué pasó -----------------------------------------------------------------
    kind: EventKind = Field(description="Tipo de evento, en vocabulario del dominio.")
    occurred_at: datetime = Field(description="Instante del cambio, en UTC.")

    # --- Señales para el análisis -------------------------------------------------
    title: str | None = Field(default=None, description="Título del elemento.")
    state: str | None = Field(default=None, description="Estado en el origen.")
    owner: str | None = Field(default=None, description="Persona responsable.")
    priority: str | None = Field(default=None, description="Prioridad declarada.")
    due_date: datetime | None = Field(default=None, description="Fecha de vencimiento.")
    estimated_hours: float | None = Field(
        default=None, ge=0, description="Estimación en horas."
    )
    labels: list[str] = Field(default_factory=list, description="Etiquetas.")
    changes: list[FieldChange] = Field(
        default_factory=list, description="Campos modificados en este evento."
    )
    comment: str | None = Field(default=None, description="Texto del comentario.")
    url: str | None = Field(default=None, description="Enlace al elemento en el origen.")

    raw_payload: dict[str, Any] = Field(
        description="Payload original del provider, sin modificar (RF-5.6)."
    )

    @property
    def fingerprint(self) -> str:
        """Huella determinística para deduplicar (RF-6.1).

        El provider forma parte del material. Sin él, dos sistemas con identificadores
        numéricos que coincidan producirían la misma huella y uno de los eventos se
        descartaría como duplicado falso.

        El instante se normaliza a UTC antes de formatearlo, para que el mismo momento
        expresado en dos zonas distintas produzca la misma huella.
        """
        moment = self.occurred_at.astimezone(UTC).isoformat()
        material = f"{self.provider.value}:{self.external_id}:{self.kind.value}:{moment}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def to_row(self, *, workspace_id: str | None) -> dict[str, Any]:
        """Convierte el evento en la fila de ``external_events``."""
        return {
            "workspace_id": workspace_id,
            "provider": self.provider.value,
            "workspace_key": self.workspace_key,
            "external_id": self.external_id,
            "external_key": self.external_key,
            "kind": self.kind.value,
            "fingerprint": self.fingerprint,
            "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
            "url": self.url,
            "raw_payload": self.raw_payload,
        }
