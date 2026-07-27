"""Servicio de análisis en vivo de Datgent.

Orquesta la ejecución secuencial de los cuatro agentes especializados, emitiendo
progreso por WebSocket a medida que cada agente completa su trabajo. El frontend
pinta la progresión sin recargar: toda la lógica ocurre aquí.

PERSISTENCIA: usa un store de sesiones en memoria (dict). Un reinicio del proceso
pierde todas las sesiones activas. Cuando el esquema de Supabase esté completo,
el servicio persiste vía repositorios; mientras tanto declara ``persistence: "memory"``
en cada respuesta.

NO ejecuta acciones externas. Aprobar una decisión la marca como ``not_started`` y
nada más: sin ejecutores registrados no hay ejecución.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.agents.risk_orchestrator import RiskOrchestrator
from app.agents.specialized import DEFAULT_AGENTS, AgentContext, BaseSpecializedAgent
from app.core.enums import StrEnum
from app.core.logging import get_logger
from app.schemas.domain import (
    ActionType,
    AgentOutput,
    AgentRunStatus,
    ApprovalStatus,
    ExecutionStatus,
    RiskCase,
)
from app.websocket.manager import ConnectionManager, EventType, WsEvent

logger = get_logger("services.live_analysis")

# Pausa entre agentes para que el frontend pueda mostrar la progresión.
# Sin ella los cuatro terminan en <1ms y no hay animación posible.
# Es una pausa de PRESENTACIÓN, no trabajo simulado.
PROGRESSIVE_DELAY_SECONDS: float = 0.8


class CerebroState(StrEnum):
    """Estados de la sesión de análisis. El frontend los muestra tal cual."""

    READY = "ready"
    STARTING_AGENTS = "starting_agents"
    GATHERING_EVIDENCE = "gathering_evidence"
    CONSOLIDATING = "consolidating"
    GENERATING_SCENARIOS = "generating_scenarios"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    PARTIAL_ERROR = "partial_error"


class LiveAgentState(StrEnum):
    """Estado de un agente individual durante el análisis en vivo."""

    WAITING = "waiting"
    INVESTIGATING = "investigating"
    COMPLETED = "completed"
    ERROR = "error"
    INSUFFICIENT_DATA = "insufficient_data"


class DomainError(Exception):
    """Error de dominio (doble aprobación, estado inválido, etc.)."""


class LiveDecision:
    """Decisión propuesta pendiente de aprobación humana."""

    def __init__(
        self,
        *,
        decision_id: UUID,
        action_type: str,
        title: str,
        rationale: str,
        payload: dict[str, Any],
        agent: str,
    ) -> None:
        self.id = decision_id
        self.action_type = action_type
        self.title = title
        self.rationale = rationale
        self.payload = payload
        self.agent = agent
        self.approval_status: ApprovalStatus = ApprovalStatus.PENDING
        self.approved_by: str | None = None
        self.approved_at: datetime | None = None
        self.rejection_reason: str | None = None
        self.execution_status: ExecutionStatus = ExecutionStatus.NOT_STARTED
        self.created_at: datetime = datetime.now(UTC)

    def approve(self, approved_by: str) -> None:
        """Aprueba la decisión. Solo desde pending; doble aprobación es error."""
        if self.approval_status != ApprovalStatus.PENDING:
            raise DomainError(
                f"No se puede aprobar: estado actual es '{self.approval_status.value}', "
                "se requiere 'pending'."
            )
        self.approval_status = ApprovalStatus.APPROVED
        self.approved_by = approved_by
        self.approved_at = datetime.now(UTC)
        # No se ejecuta nada: sin ejecutores registrados no hay ejecución.

    def reject(self, rejected_by: str, reason: str) -> None:
        """Rechaza la decisión. Solo desde pending."""
        if self.approval_status != ApprovalStatus.PENDING:
            raise DomainError(
                f"No se puede rechazar: estado actual es '{self.approval_status.value}', "
                "se requiere 'pending'."
            )
        self.approval_status = ApprovalStatus.REJECTED
        self.approved_by = rejected_by
        self.rejection_reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "action_type": self.action_type,
            "title": self.title,
            "rationale": self.rationale,
            "payload": self.payload,
            "agent": self.agent,
            "approval_status": self.approval_status.value,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejection_reason": self.rejection_reason,
            "execution_status": self.execution_status.value,
            "created_at": self.created_at.isoformat(),
        }


class LiveAgentRecord:
    """Estado y resultado de un agente durante la sesión."""

    def __init__(self, agent_name: str) -> None:
        self.agent = agent_name
        self.state: LiveAgentState = LiveAgentState.WAITING
        self.duration_ms: int = 0
        self.risk_score: int = 0
        self.severity: str = "low"
        self.confidence: float = 0.0
        self.findings_count: int = 0
        self.missing_information: list[str] = []
        self.output: AgentOutput | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "state": self.state.value,
            "duration_ms": self.duration_ms,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "confidence": self.confidence,
            "findings_count": self.findings_count,
            "missing_information": self.missing_information,
        }


class TimelineEntry:
    """Evento de timeline en memoria."""

    def __init__(
        self,
        *,
        actor_type: str,
        actor_name: str,
        event_type: str,
        summary: str,
    ) -> None:
        self.id = uuid4()
        self.actor_type = actor_type
        self.actor_name = actor_name
        self.event_type = event_type
        self.summary = summary
        self.at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "actor_type": self.actor_type,
            "actor_name": self.actor_name,
            "event_type": self.event_type,
            "summary": self.summary,
            "at": self.at.isoformat(),
        }


class LiveSession:
    """Sesión de análisis en vivo almacenada en memoria."""

    def __init__(self, session_id: UUID, *, provenance: dict[str, str]) -> None:
        self.session_id = session_id
        self.state: CerebroState = CerebroState.READY
        self.agents: list[LiveAgentRecord] = []
        self.evidence: list[dict[str, Any]] = []
        self.risk_case: RiskCase | None = None
        self.decisions: list[LiveDecision] = []
        self.timeline: list[TimelineEntry] = []
        self.agents_completed: int = 0
        self.agents_total: int = 0
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.provenance = provenance

    @property
    def is_active(self) -> bool:
        """Una sesión está activa si no ha terminado."""
        return self.state not in (
            CerebroState.COMPLETED,
            CerebroState.PARTIAL_ERROR,
            CerebroState.AWAITING_APPROVAL,
        )

    @property
    def total_duration_ms(self) -> int:
        if self.started_at is None:
            return 0
        end = self.finished_at or datetime.now(UTC)
        return int((end - self.started_at).total_seconds() * 1000)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": str(self.session_id),
            "state": self.state.value,
            "agents": [a.to_dict() for a in self.agents],
            "evidence": self.evidence,
            "risk_case": (
                self.risk_case.model_dump(mode="json") if self.risk_case else None
            ),
            "decisions": [d.to_dict() for d in self.decisions],
            "timeline": [t.to_dict() for t in self.timeline],
            "agents_completed": self.agents_completed,
            "agents_total": self.agents_total,
            "evidence_count": len(self.evidence),
            "total_duration_ms": self.total_duration_ms,
            "persistence": "memory",
            "persistence_note": (
                "El esquema de Supabase no incluye las tablas del dominio nuevo "
                "(agent_runs, findings, evidence, risk_cases, decisions, timeline_events). "
                "Los datos viven en memoria del proceso y se pierden al reiniciar."
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class LiveAnalysisService:
    """Servicio de análisis en vivo con store en memoria.

    Un reinicio del proceso pierde todas las sesiones. Cuando el esquema de Supabase
    esté aplicado se puede migrar a persistencia real sin cambiar la interfaz.
    """

    def __init__(
        self,
        ws_manager: ConnectionManager,
        *,
        progressive_delay: float = PROGRESSIVE_DELAY_SECONDS,
    ) -> None:
        self._ws = ws_manager
        self._sessions: dict[UUID, LiveSession] = {}
        self._progressive_delay = progressive_delay
        self._agents: list[BaseSpecializedAgent] = [
            agent_cls() for agent_cls in DEFAULT_AGENTS
        ]

    # --- Acceso al store -----------------------------------------------------------

    @property
    def sessions(self) -> dict[UUID, LiveSession]:
        return self._sessions

    def get_session(self, session_id: UUID) -> LiveSession | None:
        return self._sessions.get(session_id)

    def has_active_session(self) -> bool:
        """Verifica si hay alguna sesión en ejecución (evita dobles)."""
        return any(s.is_active for s in self._sessions.values())

    def get_decision(self, decision_id: UUID) -> tuple[LiveSession, LiveDecision] | None:
        """Busca una decisión en todas las sesiones."""
        for session in self._sessions.values():
            for decision in session.decisions:
                if decision.id == decision_id:
                    return session, decision
        return None

    def reset(self) -> None:
        """Limpia todas las sesiones. Solo para demo."""
        self._sessions.clear()

    # --- Broadcast seguro ----------------------------------------------------------

    async def _safe_broadcast(self, event: WsEvent) -> None:
        """Difunde sin romper el análisis si WS falla."""
        try:
            await self._ws.broadcast(event)
        except Exception as error:  # noqa: BLE001
            logger.warning("Fallo de broadcast WS: %s", type(error).__name__)

    # --- Ejecución principal -------------------------------------------------------

    async def run(
        self,
        session_id: UUID,
        context: AgentContext,
        *,
        provenance: dict[str, str],
    ) -> None:
        """Ejecuta el análisis en vivo: agentes secuenciales con emisión de progreso.

        Cada agente se ejecuta uno a uno, emitiendo eventos WS por cada evidencia y
        cambio de estado. Al final consolida el riesgo y genera decisiones.
        """
        session = LiveSession(session_id, provenance=provenance)
        self._sessions[session_id] = session
        session.started_at = datetime.now(UTC)
        session.agents_total = len(self._agents)

        # Inicializar registros de agentes
        for agent in self._agents:
            session.agents.append(LiveAgentRecord(agent.name))

        # --- starting_agents ---
        session.state = CerebroState.STARTING_AGENTS
        await self._safe_broadcast(WsEvent(
            type=EventType.ANALYSIS_STARTED,
            data={"session_id": str(session_id), "state": session.state.value},
        ))

        # --- gathering_evidence: ejecutar agentes uno a uno ---
        session.state = CerebroState.GATHERING_EVIDENCE
        outputs: list[AgentOutput] = []
        has_error = False

        for i, agent in enumerate(self._agents):
            record = session.agents[i]

            # 1. Marca investigating
            record.state = LiveAgentState.INVESTIGATING
            await self._safe_broadcast(WsEvent(
                type=EventType.AGENT_RUN_STARTED,
                data={"agent": agent.name, "session_id": str(session_id)},
            ))

            # 2. Ejecutar midiendo duration_ms
            t0 = time.perf_counter()
            try:
                output = agent.analyze(context)
            except Exception as error:  # noqa: BLE001
                # Agente que eleva -> error, los demás siguen
                t1 = time.perf_counter()
                record.state = LiveAgentState.ERROR
                record.duration_ms = int((t1 - t0) * 1000)
                has_error = True
                logger.error("Agente %s falló: %s", agent.name, error)

                await self._safe_broadcast(WsEvent(
                    type=EventType.AGENT_RUN_COMPLETED,
                    data={
                        "agent": agent.name,
                        "status": "error",
                        "risk_score": 0,
                        "severity": "low",
                        "confidence": 0.0,
                        "findings": [],
                        "duration_ms": record.duration_ms,
                    },
                ))

                # Timeline
                entry = TimelineEntry(
                    actor_type="agent",
                    actor_name=agent.name,
                    event_type="agent_run.error",
                    summary=f"El agente {agent.name} falló: {type(error).__name__}",
                )
                session.timeline.append(entry)
                await self._safe_broadcast(WsEvent(
                    type=EventType.TIMELINE_APPENDED,
                    data=entry.to_dict(),
                ))

                if i < len(self._agents) - 1:
                    await asyncio.sleep(self._progressive_delay)
                continue
            t1 = time.perf_counter()
            duration_ms = int((t1 - t0) * 1000)

            # Mapear estado
            if output.status == AgentRunStatus.SKIPPED:
                record.state = LiveAgentState.INSUFFICIENT_DATA
            else:
                record.state = LiveAgentState.COMPLETED
                session.agents_completed += 1

            record.duration_ms = duration_ms
            record.risk_score = output.risk_score
            record.severity = output.severity.value
            record.confidence = output.confidence
            record.findings_count = len(output.findings)
            record.missing_information = output.missing_information
            record.output = output
            outputs.append(output)

            # 3. Emitir evidence.created por CADA evidencia
            all_evidence = output.all_evidence
            for ev in all_evidence:
                prov = provenance.get(ev.provider, "demo")
                ev_data = {
                    "agent": agent.name,
                    "source_type": ev.source_type.value if hasattr(ev.source_type, "value") else str(ev.source_type),
                    "provider": ev.provider,
                    "external_id": ev.external_id,
                    "field": ev.field,
                    "value": ev.value,
                    "explanation": ev.explanation,
                    "observed_at": ev.observed_at.isoformat(),
                    "provenance": prov,
                }
                session.evidence.append(ev_data)
                await self._safe_broadcast(WsEvent(
                    type=EventType.EVIDENCE_CREATED,
                    data=ev_data,
                ))

            # 4. Emitir agent_run.completed
            findings_data = [
                {"code": f.code, "summary": f.summary, "risk_score": f.risk_score, "severity": f.severity.value}
                for f in output.findings
            ]
            await self._safe_broadcast(WsEvent(
                type=EventType.AGENT_RUN_COMPLETED,
                data={
                    "agent": agent.name,
                    "status": record.state.value,
                    "risk_score": output.risk_score,
                    "severity": output.severity.value,
                    "confidence": output.confidence,
                    "findings": findings_data,
                    "duration_ms": duration_ms,
                },
            ))

            # 5. Timeline
            entry = TimelineEntry(
                actor_type="agent",
                actor_name=agent.name,
                event_type="agent_run.completed",
                summary=f"{agent.name} completó: riesgo {output.risk_score}/100, {len(output.findings)} hallazgos",
            )
            session.timeline.append(entry)
            await self._safe_broadcast(WsEvent(
                type=EventType.TIMELINE_APPENDED,
                data=entry.to_dict(),
            ))

            # 6. Pausa entre agentes
            if i < len(self._agents) - 1:
                await asyncio.sleep(self._progressive_delay)

        # --- consolidating ---
        session.state = CerebroState.CONSOLIDATING
        orchestrator = RiskOrchestrator(agents=[])
        score = orchestrator.consolidate_score(outputs)
        confidence = orchestrator.consolidate_confidence(outputs)
        facts, inferences, assumptions = orchestrator.classify_claims(outputs)
        missing = orchestrator.collect_missing(outputs)
        causal_chain = orchestrator.build_causal_chain(outputs)
        premortem = orchestrator.build_premortem(context, outputs)
        summary = orchestrator.summarize(context, outputs, score)

        from app.schemas.domain import severity_for_score
        risk_case = RiskCase(
            commitment_id=context.commitment.id,
            consolidated_score=score,
            severity=severity_for_score(score),
            confidence=confidence,
            summary=summary,
            causal_chain=causal_chain,
            premortem=premortem,
            scenarios=[],
            facts=facts,
            inferences=inferences,
            assumptions=assumptions,
            missing_information=missing,
            is_partial=has_error,
            agent_outputs=outputs,
        )
        session.risk_case = risk_case

        await self._safe_broadcast(WsEvent(
            type=EventType.RISK_CASE_UPDATED,
            data={
                "session_id": str(session_id),
                "consolidated_score": score,
                "severity": risk_case.severity.value,
                "confidence": confidence,
            },
        ))

        # --- generating_scenarios ---
        session.state = CerebroState.GENERATING_SCENARIOS
        scenarios = orchestrator.build_scenarios(context, outputs, score)
        session.risk_case = RiskCase(
            commitment_id=context.commitment.id,
            consolidated_score=score,
            severity=severity_for_score(score),
            confidence=confidence,
            summary=summary,
            causal_chain=causal_chain,
            premortem=premortem,
            scenarios=scenarios,
            facts=facts,
            inferences=inferences,
            assumptions=assumptions,
            missing_information=missing,
            is_partial=has_error,
            agent_outputs=outputs,
        )

        # --- Crear decisiones propuestas ---
        for output in outputs:
            for action in output.recommended_actions:
                if action.requires_human_approval:
                    # Mapear action_type a ActionType si es válido
                    try:
                        action_type_val = ActionType(action.action_type)
                    except ValueError:
                        action_type_val = action.action_type  # type: ignore[assignment]

                    decision = LiveDecision(
                        decision_id=uuid4(),
                        action_type=action_type_val if isinstance(action_type_val, str) else action_type_val.value,
                        title=action.title,
                        rationale=action.rationale,
                        payload=action.payload,
                        agent=output.agent,
                    )
                    session.decisions.append(decision)

                    await self._safe_broadcast(WsEvent(
                        type=EventType.DECISION_CREATED,
                        data=decision.to_dict(),
                    ))

        # --- Estado final ---
        pending_decisions = [
            d for d in session.decisions
            if d.approval_status == ApprovalStatus.PENDING
        ]

        if has_error:
            session.state = CerebroState.PARTIAL_ERROR
        elif pending_decisions:
            session.state = CerebroState.AWAITING_APPROVAL
        else:
            session.state = CerebroState.COMPLETED

        session.finished_at = datetime.now(UTC)

        # Timeline final
        final_entry = TimelineEntry(
            actor_type="system",
            actor_name="cerebro",
            event_type="analysis.completed",
            summary=f"Análisis completado: riesgo {score}/100, estado {session.state.value}",
        )
        session.timeline.append(final_entry)

        await self._safe_broadcast(WsEvent(
            type=EventType.ANALYSIS_COMPLETED,
            data={
                "session_id": str(session_id),
                "state": session.state.value,
                "consolidated_score": score,
                "agents_completed": session.agents_completed,
                "agents_total": session.agents_total,
            },
        ))

    # --- Aprobación / Rechazo de decisiones ----------------------------------------

    async def approve_decision(
        self, decision_id: UUID, approved_by: str
    ) -> LiveDecision:
        """Aprueba una decisión. Emite eventos WS."""
        result = self.get_decision(decision_id)
        if result is None:
            raise KeyError(f"Decisión {decision_id} no encontrada")
        session, decision = result

        decision.approve(approved_by)

        await self._safe_broadcast(WsEvent(
            type=EventType.DECISION_APPROVED,
            data={"decision_id": str(decision_id), "approved_by": approved_by},
        ))
        await self._safe_broadcast(WsEvent(
            type=EventType.DECISION_UPDATED,
            data=decision.to_dict(),
        ))

        entry = TimelineEntry(
            actor_type="human",
            actor_name=approved_by,
            event_type="decision.approved",
            summary=f"Aprobó: {decision.title}",
        )
        session.timeline.append(entry)
        await self._safe_broadcast(WsEvent(
            type=EventType.TIMELINE_APPENDED,
            data=entry.to_dict(),
        ))

        return decision

    async def reject_decision(
        self, decision_id: UUID, rejected_by: str, reason: str
    ) -> LiveDecision:
        """Rechaza una decisión. Emite eventos WS."""
        result = self.get_decision(decision_id)
        if result is None:
            raise KeyError(f"Decisión {decision_id} no encontrada")
        session, decision = result

        decision.reject(rejected_by, reason)

        await self._safe_broadcast(WsEvent(
            type=EventType.DECISION_REJECTED,
            data={
                "decision_id": str(decision_id),
                "rejected_by": rejected_by,
                "reason": reason,
            },
        ))
        await self._safe_broadcast(WsEvent(
            type=EventType.DECISION_UPDATED,
            data=decision.to_dict(),
        ))

        entry = TimelineEntry(
            actor_type="human",
            actor_name=rejected_by,
            event_type="decision.rejected",
            summary=f"Rechazó: {decision.title} — {reason}",
        )
        session.timeline.append(entry)
        await self._safe_broadcast(WsEvent(
            type=EventType.TIMELINE_APPENDED,
            data=entry.to_dict(),
        ))

        return decision
