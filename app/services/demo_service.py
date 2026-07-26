"""Servicio del caso demo.

Crea, simula y limpia el caso demo reproducible. Los UUIDs son fijos para garantizar
idempotencia: ejecutar seed dos veces no duplica datos.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.repositories.domain import (
    CommitmentRepository,
    DocumentRepository,
    ProjectRepository,
    SourceEventRepository,
)
from app.services.rag_service import RagService

logger = get_logger("service.demo")

#: Ruta al fixture del caso demo
DEMO_CASE_PATH = Path(__file__).resolve().parent.parent.parent / "db" / "seed" / "demo_case.json"

#: UUIDs fijos del demo — usados para limpiar sin afectar otros datos
DEMO_PROJECT_ID = UUID("a0000000-0000-4000-8000-000000000001")
DEMO_COMMITMENT_ID = UUID("a0000000-0000-4000-8000-000000000002")
DEMO_EVENT_IDS = [
    UUID("a0000000-0000-4000-8000-000000000010"),
    UUID("a0000000-0000-4000-8000-000000000011"),
    UUID("a0000000-0000-4000-8000-000000000012"),
    UUID("a0000000-0000-4000-8000-000000000013"),
]
DEMO_DOCUMENT_IDS = [
    UUID("a0000000-0000-4000-8000-000000000020"),
    UUID("a0000000-0000-4000-8000-000000000021"),
]


def _load_case() -> dict[str, Any]:
    """Carga el JSON del caso demo desde disco."""
    return json.loads(DEMO_CASE_PATH.read_text(encoding="utf-8"))


class DemoService:
    """Gestión del caso demo: seed, simulate, reset."""

    def __init__(
        self,
        *,
        projects: ProjectRepository,
        commitments: CommitmentRepository,
        source_events: SourceEventRepository,
        documents: DocumentRepository,
    ) -> None:
        self._projects = projects
        self._commitments = commitments
        self._events = source_events
        self._documents = documents

    async def seed(self) -> dict[str, Any]:
        """Crea proyecto + commitment + eventos + documentos del caso demo.

        Idempotente: usa upsert con los UUIDs fijos.
        """
        case = _load_case()

        # Proyecto
        project_data = {**case["project"]}
        await self._projects.upsert(project_data, on_conflict="id")

        # Commitment
        commitment_data = {**case["commitment"]}
        await self._commitments.upsert(commitment_data, on_conflict="id")

        # Source events
        for evt in case["source_events"]:
            payload_key = evt["provider"]
            event_data = {
                **evt,
                "project_id": str(DEMO_PROJECT_ID),
                "commitment_id": str(DEMO_COMMITMENT_ID),
                "payload": case["signals"].get(payload_key, {}),
            }
            # Intentar crear; si ya existe (por event_hash), ignorar
            try:
                await self._events.upsert(event_data, on_conflict="event_hash")
            except Exception:  # noqa: BLE001 — idempotencia: duplicado no es error
                logger.debug("Evento demo %s ya existía", evt["id"])

        # Documentos
        for doc in case["documents"]:
            doc_data = {
                **doc,
                "project_id": str(DEMO_PROJECT_ID),
                "commitment_id": str(DEMO_COMMITMENT_ID),
            }
            try:
                await self._documents.upsert(doc_data, on_conflict="id")
            except Exception:  # noqa: BLE001
                logger.debug("Documento demo %s ya existía", doc["id"])

        return {
            "project_id": str(DEMO_PROJECT_ID),
            "commitment_id": str(DEMO_COMMITMENT_ID),
            "events_created": len(case["source_events"]),
            "documents_created": len(case["documents"]),
        }

    async def get_signals(self) -> dict[str, Any]:
        """Retorna las señales completas del caso demo para alimentar el análisis."""
        case = _load_case()
        return case["signals"]

    async def reset(self) -> dict[str, str]:
        """Elimina SOLO los datos del demo. No toca otros datos.

        El orden respeta FKs: hijos antes que padres.
        """
        # Documentos
        for doc_id in DEMO_DOCUMENT_IDS:
            try:
                await self._documents.delete(doc_id)
            except Exception:  # noqa: BLE001
                pass

        # Events
        for evt_id in DEMO_EVENT_IDS:
            try:
                await self._events.delete(evt_id)
            except Exception:  # noqa: BLE001
                pass

        # Commitment
        try:
            await self._commitments.delete(DEMO_COMMITMENT_ID)
        except Exception:  # noqa: BLE001
            pass

        # Proyecto
        try:
            await self._projects.delete(DEMO_PROJECT_ID)
        except Exception:  # noqa: BLE001
            pass

        return {"status": "cleaned", "commitment_id": str(DEMO_COMMITMENT_ID)}
