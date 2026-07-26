"""Repositorios del dominio Datgent.

Todos heredan de ``BaseRepository``, que ya resuelve paginacion, borrado logico y
traduccion de errores de PostgREST. Aqui solo viven las consultas propias de cada
tabla.

Estan en un unico modulo, y no uno por tabla, porque son delgados: la mayoria anade
dos o tres metodos. Repartirlos en once archivos de veinte lineas dificultaria ver el
modelo completo sin aportar aislamiento real.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from app.core.logging import get_logger
from app.repositories.base import BaseRepository, Page, Row

logger = get_logger("repository.domain")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------------
# projects
# ---------------------------------------------------------------------------------


class ProjectRepository(BaseRepository):
    """Proyectos. Raiz del modelo."""

    table_name: ClassVar[str] = "projects"
    soft_delete: ClassVar[bool] = True

    async def find_by_external_reference(self, provider: str, value: str) -> Row | None:
        """Busca el proyecto cuya referencia externa para ``provider`` coincide.

        Usa el operador de contencion de JSONB (``cs``) en lugar de traer todas las filas y
        filtrar en Python: el filtrado ocurre en la base de datos, que es donde esta el
        indice y donde el coste no crece con el numero de proyectos.
        """
        query = self._apply_soft_delete_filter(
            self._table().select("*").contains("external_references", {provider: value})
        )
        response = await self._execute(query.limit(1))
        rows = response.data or []
        return rows[0] if rows else None


# ---------------------------------------------------------------------------------
# commitments
# ---------------------------------------------------------------------------------


class CommitmentRepository(BaseRepository):
    """Compromisos: la entidad central del dominio."""

    table_name: ClassVar[str] = "commitments"
    soft_delete: ClassVar[bool] = True

    async def list_by_project(
        self, project_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> Page[Row]:
        return await self.list_page(
            limit=limit, offset=offset, filters={"project_id": str(project_id)}
        )

    async def list_at_risk(self, *, limit: int = 20, offset: int = 0) -> Page[Row]:
        """Compromisos marcados en riesgo, los mas urgentes primero.

        Ordena por ``due_date`` ascendente y no por ``created_at``: lo que importa de un
        compromiso en riesgo es cuanto falta para su vencimiento.
        """
        return await self.list_page(
            limit=limit,
            offset=offset,
            filters={"status": "at_risk"},
            order_column="due_date",
            descending=False,
        )

    async def set_status(self, commitment_id: UUID, status: str) -> Row:
        return await self.update(commitment_id, {"status": status})


# ---------------------------------------------------------------------------------
# provider_connections
# ---------------------------------------------------------------------------------


class ProviderConnectionRepository(BaseRepository):
    """Estado de la conexion a cada sistema externo."""

    table_name: ClassVar[str] = "provider_connections"

    async def upsert_status(
        self,
        *,
        provider: str,
        project_id: UUID | None,
        status: str,
        last_error: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Row:
        """Registra el estado de un provider.

        ``config`` nunca debe traer secretos: solo parametros no sensibles y referencias al
        nombre de la variable de entorno que los guarda.
        """
        payload: Row = {
            "provider": provider,
            "project_id": str(project_id) if project_id else None,
            "status": status,
            "last_error": last_error,
        }
        if config is not None:
            payload["config"] = config
        if status == "connected":
            payload["last_sync_at"] = _utc_now_iso()
        return await self.upsert(payload, on_conflict="project_id,provider")


# ---------------------------------------------------------------------------------
# source_events
# ---------------------------------------------------------------------------------


class SourceEventRepository(BaseRepository):
    """Eventos crudos de providers, deduplicados por ``event_hash``."""

    table_name: ClassVar[str] = "source_events"
    default_order_column: ClassVar[str] = "occurred_at"

    async def find_by_hash(self, event_hash: str) -> Row | None:
        return await self.find_one({"event_hash": event_hash})

    async def list_recent_for_commitment(
        self, commitment_id: UUID, *, limit: int = 20
    ) -> list[Row]:
        """Historial reciente de un compromiso, del mas nuevo al mas antiguo.

        Alimenta las senales que solo se ven en el historico, como el estancamiento: un
        agente que solo mira el evento actual no puede detectar "sin actividad en 5 dias".
        """
        query = (
            self._table()
            .select("*")
            .eq("commitment_id", str(commitment_id))
            .order("occurred_at", desc=True)
            .limit(max(1, min(limit, 100)))
        )
        response = await self._execute(query)
        return response.data or []

    async def mark_processed(self, event_id: UUID) -> Row:
        return await self.update(event_id, {"processing_status": "processed"})

    async def mark_failed(self, event_id: UUID, error: str) -> Row:
        """Marca el evento como fallido guardando un motivo acotado.

        El error se trunca: los mensajes de librerias externas pueden ser enormes y no
        tiene sentido guardar una traza completa en una columna de estado.
        """
        return await self.update(
            event_id,
            {"processing_status": "failed", "processing_error": error[:500]},
        )

    async def list_pending(self, *, limit: int = 50) -> list[Row]:
        """Eventos sin procesar. Respalda la reconciliacion manual de eventos perdidos."""
        query = (
            self._table()
            .select("*")
            .in_("processing_status", ["pending", "failed"])
            .order("occurred_at", desc=False)
            .limit(max(1, min(limit, 100)))
        )
        response = await self._execute(query)
        return response.data or []


# ---------------------------------------------------------------------------------
# agent_runs
# ---------------------------------------------------------------------------------


class AgentRunRepository(BaseRepository):
    """Ejecuciones de agentes. Unidad de auditoria del analisis."""

    table_name: ClassVar[str] = "agent_runs"

    async def start(
        self,
        *,
        agent_name: str,
        commitment_id: UUID | None,
        model: str | None = None,
        prompt_version: str | None = None,
        input_reference: str | None = None,
    ) -> Row:
        """Abre una ejecucion en estado ``running``.

        Se crea antes de ejecutar, no despues: si el agente muere sin devolver nada, la
        fila queda como rastro de que se intento.
        """
        return await self.create(
            {
                "agent_name": agent_name,
                "commitment_id": str(commitment_id) if commitment_id else None,
                "status": "running",
                "started_at": _utc_now_iso(),
                "model": model,
                "prompt_version": prompt_version,
                "input_reference": input_reference,
            }
        )

    async def finish(
        self,
        run_id: UUID,
        *,
        output: dict[str, Any],
        duration_ms: int | None = None,
    ) -> Row:
        return await self.update(
            run_id,
            {
                "status": "completed",
                "finished_at": _utc_now_iso(),
                "output": output,
                "duration_ms": duration_ms,
            },
        )

    async def fail(self, run_id: UUID, error: str) -> Row:
        return await self.update(
            run_id,
            {
                "status": "failed",
                "finished_at": _utc_now_iso(),
                "error": error[:1000],
            },
        )

    async def list_for_commitment(
        self, commitment_id: UUID, *, limit: int = 20
    ) -> list[Row]:
        query = (
            self._table()
            .select("*")
            .eq("commitment_id", str(commitment_id))
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 100)))
        )
        response = await self._execute(query)
        return response.data or []


# ---------------------------------------------------------------------------------
# findings + evidence
# ---------------------------------------------------------------------------------


class FindingRepository(BaseRepository):
    """Hallazgos producidos por los agentes."""

    table_name: ClassVar[str] = "findings"

    async def list_for_commitment(
        self, commitment_id: UUID, *, limit: int = 50
    ) -> list[Row]:
        query = (
            self._table()
            .select("*")
            .eq("commitment_id", str(commitment_id))
            .order("risk_score", desc=True)
            .limit(max(1, min(limit, 100)))
        )
        response = await self._execute(query)
        return response.data or []


class EvidenceRepository(BaseRepository):
    """Evidencia que respalda cada hallazgo."""

    table_name: ClassVar[str] = "evidence"
    default_order_column: ClassVar[str] = "observed_at"

    async def create_many(self, rows: list[Row]) -> list[Row]:
        """Inserta varias evidencias en una sola llamada.

        Una insercion por evidencia significaria una ida y vuelta a PostgREST por cada
        campo observado, y un analisis genera decenas.
        """
        if not rows:
            return []
        response = await self._execute(self._table().insert(rows))
        return response.data or []

    async def list_for_finding(self, finding_id: UUID) -> list[Row]:
        query = (
            self._table()
            .select("*")
            .eq("finding_id", str(finding_id))
            .order("observed_at", desc=True)
        )
        response = await self._execute(query)
        return response.data or []


# ---------------------------------------------------------------------------------
# risk_cases
# ---------------------------------------------------------------------------------


class RiskCaseRepository(BaseRepository):
    """Riesgo consolidado por compromiso: la salida del orquestador."""

    table_name: ClassVar[str] = "risk_cases"

    async def latest_for_commitment(self, commitment_id: UUID) -> Row | None:
        """Ultimo caso de riesgo de un compromiso."""
        query = (
            self._table()
            .select("*")
            .eq("commitment_id", str(commitment_id))
            .order("created_at", desc=True)
            .limit(1)
        )
        response = await self._execute(query)
        rows = response.data or []
        return rows[0] if rows else None


# ---------------------------------------------------------------------------------
# alerts
# ---------------------------------------------------------------------------------


class AlertRepository(BaseRepository):
    """Alertas derivadas de casos de riesgo."""

    table_name: ClassVar[str] = "alerts"
    soft_delete: ClassVar[bool] = True

    async def find_open_for_commitment(self, commitment_id: UUID) -> Row | None:
        return await self.find_one(
            {"commitment_id": str(commitment_id), "status": "open"}
        )

    async def acknowledge(self, alert_id: UUID, acknowledged_by: str) -> Row:
        return await self.update(
            alert_id,
            {
                "status": "acknowledged",
                "acknowledged_by": acknowledged_by,
                "acknowledged_at": _utc_now_iso(),
            },
        )

    async def resolve(self, alert_id: UUID) -> Row:
        """Resuelve una alerta.

        Rellena ``acknowledged_at`` si estaba vacio porque la restriccion ``check`` del
        esquema lo exige para los estados distintos de ``open``: resolver sin reconocer
        seria un estado que la base de datos rechaza.
        """
        now = _utc_now_iso()
        return await self.update(
            alert_id,
            {"status": "resolved", "resolved_at": now, "acknowledged_at": now},
        )


# ---------------------------------------------------------------------------------
# decisions
# ---------------------------------------------------------------------------------


class DecisionRepository(BaseRepository):
    """Acciones propuestas que requieren aprobacion humana."""

    table_name: ClassVar[str] = "decisions"

    async def approve(self, decision_id: UUID, approved_by: str) -> Row:
        return await self.update(
            decision_id,
            {
                "approval_status": "approved",
                "approved_by": approved_by,
                "approved_at": _utc_now_iso(),
            },
        )

    async def reject(self, decision_id: UUID, rejected_by: str, reason: str) -> Row:
        return await self.update(
            decision_id,
            {
                "approval_status": "rejected",
                "approved_by": rejected_by,
                "rejection_reason": reason[:1000],
            },
        )

    async def mark_execution(
        self,
        decision_id: UUID,
        *,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Row:
        payload: Row = {"execution_status": status}
        if result is not None:
            payload["execution_result"] = result
        if error is not None:
            payload["error"] = error[:1000]
        if status in {"succeeded", "failed"}:
            payload["executed_at"] = _utc_now_iso()
        return await self.update(decision_id, payload)

    async def list_pending(self, *, limit: int = 20, offset: int = 0) -> Page[Row]:
        return await self.list_page(
            limit=limit, offset=offset, filters={"approval_status": "pending"}
        )


# ---------------------------------------------------------------------------------
# timeline_events
# ---------------------------------------------------------------------------------


class TimelineRepository(BaseRepository):
    """Historia legible de un compromiso."""

    table_name: ClassVar[str] = "timeline_events"

    async def append(
        self,
        *,
        commitment_id: UUID,
        actor_type: str,
        actor_name: str,
        event_type: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> Row:
        return await self.create(
            {
                "commitment_id": str(commitment_id),
                "actor_type": actor_type,
                "actor_name": actor_name,
                "event_type": event_type,
                "summary": summary,
                "payload": payload or {},
            }
        )

    async def list_for_commitment(
        self, commitment_id: UUID, *, limit: int = 50
    ) -> list[Row]:
        query = (
            self._table()
            .select("*")
            .eq("commitment_id", str(commitment_id))
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 200)))
        )
        response = await self._execute(query)
        return response.data or []


# ---------------------------------------------------------------------------------
# documents (RAG)
# ---------------------------------------------------------------------------------


class DocumentRepository(BaseRepository):
    """Documentos y fragmentos recuperables."""

    table_name: ClassVar[str] = "documents"

    async def search_fulltext(
        self,
        query_text: str,
        *,
        project_id: UUID | None = None,
        commitment_id: UUID | None = None,
        limit: int = 5,
    ) -> list[Row]:
        """Recuperacion textual sobre ``content``.

        Usa ``ilike`` y no ``text_search`` de PostgREST a proposito: ``ilike`` funciona sin
        depender de que el indice de full-text search este creado ni de que la
        configuracion de idioma coincida. Es menos preciso, pero no se rompe segun el
        estado del esquema, y el RAG minimo tiene que funcionar en un Supabase recien
        aplicado.
        """
        needle = query_text.strip()
        if not needle:
            return []

        db_query = self._table().select("*")
        if project_id:
            db_query = db_query.eq("project_id", str(project_id))
        if commitment_id:
            db_query = db_query.eq("commitment_id", str(commitment_id))

        db_query = db_query.ilike("content", f"%{needle}%").limit(
            max(1, min(limit, 20))
        )
        response = await self._execute(db_query)
        return response.data or []

    async def list_for_commitment(self, commitment_id: UUID) -> list[Row]:
        query = self._table().select("*").eq("commitment_id", str(commitment_id))
        response = await self._execute(query)
        return response.data or []
