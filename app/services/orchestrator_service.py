"""Servicio orquestador.

Único coordinador de providers. Es la pieza que resuelve el provider en el registro, recoge los
eventos por el puerto, compone el contexto desde los repositorios e invoca al orquestador de
agentes.

Tiene E/S; el ``OrchestratorAgent`` no. Esa frontera es la que permite probar toda la lógica de
riesgo sin levantar nada.

No importa ningún provider concreto: solo el puerto y el registro. Añadir GitHub no toca este
archivo.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.agents.base import AgentContext
from app.agents.orchestrator import OrchestratorAgent
from app.core.exceptions import EntityNotFoundError, InvalidRequestError
from app.core.logging import get_logger
from app.providers.base import RepositoryBundle
from app.providers.registry import ProviderRegistry
from app.schemas.analysis import (
    AnalysisResult,
    CommitmentSnapshot,
    CommitmentStatus,
    ProjectSnapshot,
)
from app.schemas.events import EventKind, ExternalEvent, ProviderName
from app.schemas.providers import SyncReport, SyncRequest
from app.services.ingest_service import IngestOutcome, IngestService

logger = get_logger("orchestrator")


class OrchestratorService:
    """Coordina providers, persistencia y agentes."""

    def __init__(
        self,
        registry: ProviderRegistry,
        repositories: RepositoryBundle,
        ingest: IngestService,
        agent: OrchestratorAgent | None = None,
        *,
        alert_threshold: int = 70,
    ) -> None:
        self._registry = registry
        self._repos = repositories
        self._ingest = ingest
        self._agent = agent or OrchestratorAgent()
        self._threshold = alert_threshold

    # --- Sincronización -----------------------------------------------------------

    async def sync(self, provider_name: ProviderName | str, request: SyncRequest) -> SyncReport:
        """Sincroniza un contenedor a través del provider indicado (RF-4).

        El provider dirige el recorrido y este servicio le presta el sumidero que persiste. Así
        la integración no conoce el almacenamiento y el servicio no conoce la paginación.
        """
        provider = self._registry.get(provider_name)
        return await provider.sync(request, self._ingest.sink)

    # --- Webhooks -----------------------------------------------------------------

    async def handle_webhook(
        self,
        provider_name: ProviderName | str,
        payload: dict[str, Any],
        headers: dict[str, str],
        params: dict[str, str],
    ) -> IngestOutcome:
        """Valida, traduce y persiste una entrega de webhook (RF-5).

        La validación va primero: un payload no autenticado no debe llegar a persistirse ni a
        procesarse (RF-5.2). Cada provider la implementa a su manera, y por eso vive en el puerto
        y no aquí: este método no tiene ninguna rama por provider.
        """
        provider = self._registry.get(provider_name)
        provider.verify_webhook(headers, params)
        event = provider.parse_webhook(payload)
        return await self._ingest.ingest(event)

    # --- Análisis -----------------------------------------------------------------

    async def analyse_event(self, event: ExternalEvent, *, event_id: UUID | None) -> AnalysisResult:
        """Analiza un evento y persiste el resultado.

        Deriva el compromiso desde el evento antes de analizar, porque el análisis necesita saber
        qué se prometió y para cuándo.
        """
        context = await self._build_context(event)
        result = self._agent.analyse(context)

        commitment_id = context.commitment.id if context.commitment else None
        await self._repos.analyses.record(
            risk_score=result.risk_score,
            severity=result.severity.value,
            findings=result.findings(),
            event_id=event_id,
            commitment_id=commitment_id,
            is_partial=result.is_partial,
        )

        logger.info(
            "Análisis de %s: riesgo=%d severidad=%s parcial=%s",
            event.external_key,
            result.risk_score,
            result.severity.value,
            result.is_partial,
        )
        return result

    async def analyse_outcome(self, outcome: IngestOutcome) -> AnalysisResult:
        """Analiza el resultado de una ingesta. Es el trabajo posterior al webhook."""
        return await self.analyse_event(outcome.event, event_id=outcome.event_id)

    async def analyse_target(
        self,
        *,
        event_id: UUID | None = None,
        provider_name: ProviderName | str | None = None,
        workspace_key: str | None = None,
    ) -> AnalysisResult:
        """Relanza el análisis sobre un evento o sobre el último de un contenedor (RF-11).

        Sin ninguno de los dos, ``422``: pedir "analiza algo" sin decir qué no es una petición
        válida (RF-11.4).
        """
        if event_id is None and workspace_key is None:
            raise InvalidRequestError(
                "Indica un evento o un contenedor para analizar."
            )

        row = (
            await self._repos.events.get_or_raise(event_id)
            if event_id is not None
            else await self._latest_event_row(provider_name, workspace_key)
        )
        event = self._event_from_row(row)
        return await self.analyse_event(event, event_id=UUID(str(row["id"])))

    async def _latest_event_row(
        self, provider_name: ProviderName | str | None, workspace_key: str | None
    ) -> dict[str, Any]:
        if provider_name is None or workspace_key is None:
            raise InvalidRequestError(
                "Para analizar por contenedor hacen falta el provider y su clave."
            )
        provider = ProviderName(provider_name)
        workspace = await self._repos.workspaces.get_by_key_or_raise(
            provider, workspace_key
        )
        row = await self._repos.events.get_latest_for_workspace(
            UUID(str(workspace["id"]))
        )
        if row is None:
            raise EntityNotFoundError(
                "El contenedor no tiene eventos que analizar.",
                details={"workspace_key": workspace_key},
            )
        return row

    # --- Composición del contexto -------------------------------------------------

    async def _build_context(self, event: ExternalEvent) -> AgentContext:
        """Reúne desde los repositorios lo que los agentes necesitan.

        Los agentes no leen de la base de datos: reciben el contexto ya compuesto. Es lo que los
        mantiene puros (RF-8.3).
        """
        workspace = await self._repos.workspaces.ensure(
            provider=event.provider,
            workspace_key=event.workspace_key,
            name=event.workspace_key,
        )
        workspace_id = UUID(str(workspace["id"]))

        project = ProjectSnapshot(
            id=workspace_id,
            jira_project_key=str(workspace.get("workspace_key") or event.workspace_key),
            hourly_cost=float(workspace.get("hourly_cost") or 0.0),
        )

        commitment = await self._upsert_commitment(event, workspace_id)
        history = await self._repos.events.list_by_external_key(
            event.provider, event.external_key, limit=10
        )

        return AgentContext(
            event=event,
            now=datetime.now(UTC),
            commitment=commitment,
            project=project,
            recent_events=[
                self._event_from_row(row)
                for row in history.items
                if row.get("fingerprint") != event.fingerprint
            ],
        )

    async def _upsert_commitment(
        self, event: ExternalEvent, workspace_id: UUID
    ) -> CommitmentSnapshot | None:
        """Deriva el compromiso desde el evento.

        Solo los elementos de trabajo representan compromisos: un comentario o un cambio de
        estado de despliegue no crean uno nuevo, aunque sí alimenten el análisis del existente.
        """
        if event.kind not in {
            EventKind.WORK_ITEM_CREATED,
            EventKind.WORK_ITEM_UPDATED,
        }:
            existing = await self._repos.commitments.get_by_issue_key(
                workspace_id, event.external_key
            )
            return self._commitment_from_row(existing) if existing else None

        row = await self._repos.commitments.upsert_from_issue(
            workspace_id=workspace_id,
            provider=event.provider.value,
            external_key=event.external_key,
            title=event.title or event.external_key,
            due_date=event.due_date.isoformat() if event.due_date else None,
            estimated_hours=event.estimated_hours,
        )
        return self._commitment_from_row(row)

    @staticmethod
    def _commitment_from_row(row: dict[str, Any]) -> CommitmentSnapshot:
        return CommitmentSnapshot(
            id=UUID(str(row["id"])) if row.get("id") else None,
            jira_issue_key=str(row.get("external_key") or ""),
            title=str(row.get("title") or ""),
            due_date=row.get("due_date"),
            status=CommitmentStatus(str(row.get("status") or "open")),
            estimated_hours=row.get("estimated_hours"),
        )

    @staticmethod
    def _event_from_row(row: dict[str, Any]) -> ExternalEvent:
        """Reconstruye el evento desde su fila.

        El payload original se guardó intacto, así que el evento se puede rehidratar sin volver a
        llamar al provider. Es lo que permite reanalizar sin depender de que Jira esté disponible.
        """
        return ExternalEvent(
            provider=ProviderName(str(row["provider"])),
            workspace_key=str(row["workspace_key"]),
            external_id=str(row["external_id"]),
            external_key=str(row["external_key"]),
            kind=EventKind(str(row["kind"])),
            occurred_at=row["occurred_at"],
            url=row.get("url"),
            raw_payload=row.get("raw_payload") or {},
        )
