"""Servicio de análisis de compromisos.

Es la frontera entre el orquestador puro y el mundo: recolecta señales de los providers,
invoca al orquestador, persiste el resultado, decide si abre alerta, crea las decisiones
que requieren aprobación y difunde por WebSocket.

El orquestador no hace nada de esto a propósito. Separarlo es lo que permite probar toda
la lógica de riesgo sin levantar Supabase, y lo que hace que cambiar el mecanismo de
difusión no toque el cálculo.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.agents.risk_orchestrator import RiskOrchestrator
from app.agents.specialized import AgentContext
from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.repositories.domain import (
    AgentRunRepository,
    AlertRepository,
    CommitmentRepository,
    DecisionRepository,
    DocumentRepository,
    EvidenceRepository,
    FindingRepository,
    ProjectRepository,
    RiskCaseRepository,
    SourceEventRepository,
    TimelineRepository,
)
from app.schemas.domain import (
    AgentOutput,
    CommitmentSnapshot,
    ProjectSnapshot,
    RetrievedChunk,
    RiskCase,
)
from app.websocket.manager import ConnectionManager, EventType, WsEvent

logger = get_logger("service.analysis")


class AnalysisService:
    """Ejecuta el análisis completo de un compromiso y publica el resultado."""

    def __init__(
        self,
        *,
        projects: ProjectRepository,
        commitments: CommitmentRepository,
        source_events: SourceEventRepository,
        agent_runs: AgentRunRepository,
        findings: FindingRepository,
        evidence: EvidenceRepository,
        risk_cases: RiskCaseRepository,
        alerts: AlertRepository,
        decisions: DecisionRepository,
        timeline: TimelineRepository,
        documents: DocumentRepository,
        ws_manager: ConnectionManager,
        risk_alert_threshold: int = 70,
        orchestrator: RiskOrchestrator | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self._projects = projects
        self._commitments = commitments
        self._source_events = source_events
        self._agent_runs = agent_runs
        self._findings = findings
        self._evidence = evidence
        self._risk_cases = risk_cases
        self._alerts = alerts
        self._decisions = decisions
        self._timeline = timeline
        self._documents = documents
        self._ws = ws_manager
        self._threshold = risk_alert_threshold
        self._orchestrator = orchestrator or RiskOrchestrator()
        self._llm = llm
        #: Identificador de ejecución por agente, poblado durante el análisis. Liga cada
        #: hallazgo persistido con el ``agent_run`` que lo produjo. Es estado por
        #: análisis, no compartido: se reinicia en cada llamada a ``analyze_commitment``.
        self._run_ids: dict[str, UUID] = {}

    # --- Punto de entrada ----------------------------------------------------------

    async def analyze_commitment(
        self, commitment_id: UUID, *, signals: dict[str, Any] | None = None
    ) -> RiskCase:
        """Analiza un compromiso de principio a fin.

        ``signals`` permite inyectar las señales ya recolectadas. Cuando no se pasan, se
        recogen de los eventos persistidos: así el mismo flujo sirve para un análisis
        disparado por webhook (que ya tiene la señal fresca) y para uno pedido a mano.
        """
        commitment_row = await self._commitments.get_or_raise(commitment_id)
        project_row = await self._projects.get(UUID(commitment_row["project_id"]))

        # Estado por análisis: dos llamadas seguidas sobre la misma instancia no deben
        # ligar los hallazgos de la segunda a las ejecuciones de la primera.
        self._run_ids = {}

        await self._broadcast(
            EventType.ANALYSIS_STARTED,
            commitment_id=commitment_id,
            project_id=project_row["id"] if project_row else None,
            data={"commitment_title": commitment_row.get("title")},
        )

        context = await self._build_context(commitment_row, project_row, signals)

        outputs = await self._run_and_record_agents(context, commitment_id)
        risk_case = self._compose(context, outputs)
        risk_case = await self._enrich_with_llm(context, risk_case)

        risk_case_row = await self._persist_risk_case(risk_case, commitment_id)
        risk_case_id = UUID(risk_case_row["id"])

        await self._persist_findings(outputs, commitment_id)
        await self._maybe_open_alert(risk_case, commitment_id, risk_case_id)
        await self._create_decisions(outputs, commitment_id, risk_case_id)
        await self._sync_commitment_status(risk_case, commitment_id)

        await self._timeline.append(
            commitment_id=commitment_id,
            actor_type="agent",
            actor_name=self._orchestrator.name,
            event_type="analysis.completed",
            summary=risk_case.summary,
            payload={
                "consolidated_score": risk_case.consolidated_score,
                "severity": risk_case.severity.value,
                "is_partial": risk_case.is_partial,
            },
        )

        await self._broadcast(
            EventType.RISK_CASE_CREATED,
            commitment_id=commitment_id,
            risk_case_id=risk_case_id,
            project_id=project_row["id"] if project_row else None,
            data={
                "consolidated_score": risk_case.consolidated_score,
                "severity": risk_case.severity.value,
                "summary": risk_case.summary,
                "is_partial": risk_case.is_partial,
                "scenarios": len(risk_case.scenarios),
            },
        )

        return risk_case

    # --- Contexto ------------------------------------------------------------------

    async def _build_context(
        self,
        commitment_row: dict[str, Any],
        project_row: dict[str, Any] | None,
        signals: dict[str, Any] | None,
    ) -> AgentContext:
        commitment_id = UUID(commitment_row["id"])

        recent = await self._source_events.list_recent_for_commitment(commitment_id)

        # Si no se pasaron señales, se derivan del último evento de cada provider. Un
        # evento viejo sigue siendo información: lo que no vale es inventarla.
        resolved_signals = signals if signals is not None else self._signals_from_events(recent)

        documents = await self._retrieve_documents(commitment_row, commitment_id)

        return AgentContext(
            commitment=CommitmentSnapshot(
                id=commitment_id,
                project_id=UUID(commitment_row["project_id"]),
                title=commitment_row["title"],
                description=commitment_row.get("description"),
                beneficiary=commitment_row.get("beneficiary"),
                owner=commitment_row.get("owner"),
                due_date=_as_datetime(commitment_row.get("due_date")),
                financial_exposure=Decimal(str(commitment_row.get("financial_exposure") or 0)),
                currency=commitment_row.get("currency") or "USD",
                metadata=commitment_row.get("metadata") or {},
            ),
            project=(
                ProjectSnapshot(
                    id=UUID(project_row["id"]),
                    name=project_row["name"],
                    hourly_cost=Decimal(str(project_row.get("hourly_cost") or 0)),
                    currency=project_row.get("currency") or "USD",
                    external_references=project_row.get("external_references") or {},
                )
                if project_row
                else None
            ),
            now=datetime.now(UTC),
            signals=resolved_signals,
            recent_events=recent,
            documents=documents,
        )

    @staticmethod
    def _signals_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
        """Agrupa el payload del evento más reciente de cada provider.

        Solo el más reciente: un agente que recibiera el histórico completo tendría que
        decidir qué versión de cada campo es la vigente, y esa decisión pertenece aquí.
        """
        signals: dict[str, Any] = {}
        for event in events:  # ya vienen del más nuevo al más antiguo
            provider = event.get("provider")
            if provider and provider not in signals:
                signals[provider] = event.get("payload") or {}
        return signals

    async def _retrieve_documents(
        self, commitment_row: dict[str, Any], commitment_id: UUID
    ) -> list[RetrievedChunk]:
        """Recupera contexto documental relevante para el compromiso.

        Un fallo de recuperación no detiene el análisis: el RAG aporta contexto
        contractual útil, pero el riesgo se puede calcular sin él.
        """
        try:
            rows = await self._documents.search_fulltext(
                commitment_row.get("title", ""), commitment_id=commitment_id, limit=3
            )
        except Exception as error:  # noqa: BLE001 - el RAG es opcional
            logger.warning("Recuperación documental fallida: %s", type(error).__name__)
            return []

        return [
            RetrievedChunk(
                document_id=UUID(row["id"]) if row.get("id") else None,
                title=row.get("title", ""),
                content=row.get("content", "")[:2000],
                score=1.0,
                strategy="fulltext",
                source_url=row.get("source_url"),
            )
            for row in rows
        ]

    # --- Ejecución de agentes ------------------------------------------------------

    async def _run_and_record_agents(
        self, context: AgentContext, commitment_id: UUID
    ) -> list[AgentOutput]:
        """Ejecuta cada agente registrando su ``agent_run``.

        El registro se abre antes de ejecutar y se cierra después. Si el agente muere, la
        fila queda en ``failed`` con el motivo: sin eso, un agente que revienta es
        indistinguible de uno que nunca se lanzó.
        """
        outputs: list[AgentOutput] = []

        for agent in self._orchestrator._agents:  # noqa: SLF001 - mismo módulo lógico
            run_row = await self._agent_runs.start(
                agent_name=agent.name,
                commitment_id=commitment_id,
                model=getattr(self._llm, "name", None) if self._llm else None,
                input_reference=f"commitment:{commitment_id}",
            )
            run_id = UUID(run_row["id"])
            started = time.perf_counter()

            try:
                output = agent.analyze(context)
            except Exception as error:  # noqa: BLE001 - un agente caído no tumba el análisis
                logger.error("El agente %s falló", agent.name, exc_info=error)
                await self._agent_runs.fail(run_id, f"{type(error).__name__}: {error}")
                continue

            duration_ms = int((time.perf_counter() - started) * 1000)
            await self._agent_runs.finish(
                run_id, output=output.model_dump(mode="json"), duration_ms=duration_ms
            )
            # El identificador del run viaja en los metadatos para poder ligar los
            # hallazgos persistidos con la ejecución que los produjo.
            outputs.append(output.model_copy(update={"commitment_id": commitment_id}))
            self._run_ids[output.agent] = run_id

            await self._broadcast(
                EventType.AGENT_RUN_COMPLETED,
                commitment_id=commitment_id,
                data={
                    "agent": output.agent,
                    "risk_score": output.risk_score,
                    "severity": output.severity.value,
                    "status": output.status.value,
                    "findings": len(output.findings),
                    "duration_ms": duration_ms,
                },
            )

        return outputs

    # --- Composición y enriquecimiento ---------------------------------------------

    def _compose(self, context: AgentContext, outputs: list[AgentOutput]) -> RiskCase:
        """Compone el caso determinístico a partir de las salidas ya obtenidas.

        No se llama a ``orchestrator.analyze`` porque eso volvería a ejecutar los
        agentes, y aquí ya se ejecutaron con su registro de auditoría.
        """
        orch = self._orchestrator
        score = orch.consolidate_score(outputs)
        facts, inferences, assumptions = orch.classify_claims(outputs)

        from app.schemas.domain import severity_for_score

        expected = len(orch._agents)  # noqa: SLF001
        return RiskCase(
            commitment_id=context.commitment.id,
            consolidated_score=score,
            severity=severity_for_score(score),
            confidence=orch.consolidate_confidence(outputs),
            summary=orch.summarize(context, outputs, score),
            causal_chain=orch.build_causal_chain(outputs),
            premortem=orch.build_premortem(context, outputs),
            scenarios=orch.build_scenarios(context, outputs, score),
            facts=facts,
            inferences=inferences,
            assumptions=assumptions,
            missing_information=orch.collect_missing(outputs),
            # Faltan salidas respecto a los agentes registrados: alguno reventó.
            is_partial=len(outputs) < expected,
            agent_outputs=outputs,
        )

    async def _enrich_with_llm(
        self, context: AgentContext, risk_case: RiskCase
    ) -> RiskCase:
        """Sustituye la narrativa por la del LLM, si hay uno disponible.

        La puntuación NO se toca: es determinística por diseño. El LLM mejora la
        explicación, no el juicio. Si falla, se conserva la narrativa por reglas, que ya
        es utilizable.

        El contexto se construye con ``build_context``, que sanitiza recursivamente las
        claves sensibles. Se le pasan hallazgos y evidencia aplanados, no las salidas
        completas de los agentes: enviar el objeto entero incluiría campos que el modelo
        no necesita y ampliaría la superficie de fuga sin mejorar la respuesta.
        """
        if self._llm is None or not self._llm.is_available():
            return risk_case

        try:
            from app.llm.prompts import BUSINESS_EXPLANATION_SYSTEM, build_context

            findings = [
                finding.model_dump(mode="json", exclude={"evidence"})
                for output in risk_case.agent_outputs
                for finding in output.findings
            ]
            evidence = [
                ev.model_dump(mode="json")
                for output in risk_case.agent_outputs
                for ev in output.all_evidence
            ]

            payload = build_context(
                commitment=context.commitment.model_dump(mode="json"),
                findings=findings,
                evidence=evidence,
                metadata={
                    "consolidated_score": risk_case.consolidated_score,
                    "severity": risk_case.severity.value,
                    "is_partial": risk_case.is_partial,
                    "missing_information": risk_case.missing_information,
                },
            )
            response = await self._llm.complete(
                BUSINESS_EXPLANATION_SYSTEM, payload, max_tokens=600
            )
            content = response.content.strip()
            # Una respuesta vacía no mejora nada: conservar la narrativa por reglas es
            # mejor que dejar el caso sin resumen.
            return risk_case.model_copy(update={"summary": content}) if content else risk_case
        except Exception as error:  # noqa: BLE001 - el LLM es opcional por diseño
            logger.warning(
                "Enriquecimiento con LLM no disponible: %s", type(error).__name__
            )
            return risk_case

    # --- Persistencia --------------------------------------------------------------

    async def _persist_risk_case(
        self, risk_case: RiskCase, commitment_id: UUID
    ) -> dict[str, Any]:
        return await self._risk_cases.create(
            {
                "commitment_id": str(commitment_id),
                "consolidated_score": risk_case.consolidated_score,
                "severity": risk_case.severity.value,
                "confidence": float(risk_case.confidence),
                "causal_chain": [s.model_dump(mode="json") for s in risk_case.causal_chain],
                "premortem": (
                    risk_case.premortem.model_dump(mode="json")
                    if risk_case.premortem
                    else {}
                ),
                "scenarios": [s.model_dump(mode="json") for s in risk_case.scenarios],
                "facts": risk_case.facts,
                "inferences": risk_case.inferences,
                "assumptions": risk_case.assumptions,
                "missing_information": risk_case.missing_information,
                "summary": risk_case.summary,
                "is_partial": risk_case.is_partial,
            }
        )

    async def _persist_findings(
        self, outputs: list[AgentOutput], commitment_id: UUID
    ) -> None:
        """Guarda hallazgos y su evidencia.

        La evidencia se inserta en lote por hallazgo: una llamada por evidencia
        multiplicaría las idas y vueltas a PostgREST, y un análisis genera decenas.
        """
        for output in outputs:
            run_id = self._run_ids.get(output.agent)
            if run_id is None:
                continue

            for finding in output.findings:
                finding_row = await self._findings.create(
                    {
                        "agent_run_id": str(run_id),
                        "commitment_id": str(commitment_id),
                        "category": finding.category,
                        "code": finding.code,
                        "severity": finding.severity.value,
                        "risk_score": finding.risk_score,
                        "confidence": float(finding.confidence),
                        "summary": finding.summary,
                        "impact": finding.impact,
                    }
                )
                if finding.evidence:
                    await self._evidence.create_many(
                        [
                            {
                                "finding_id": finding_row["id"],
                                "provider": ev.provider,
                                "source_type": ev.source_type.value,
                                "external_id": ev.external_id,
                                "source_url": ev.source_url,
                                "field": ev.field,
                                "value": ev.value,
                                "content": ev.content,
                                "metadata": {"explanation": ev.explanation},
                                "observed_at": ev.observed_at.isoformat(),
                            }
                            for ev in finding.evidence
                        ]
                    )

    # --- Alertas y decisiones ------------------------------------------------------

    async def _maybe_open_alert(
        self, risk_case: RiskCase, commitment_id: UUID, risk_case_id: UUID
    ) -> None:
        """Abre, actualiza o resuelve la alerta según el umbral configurado.

        Actualizar la alerta abierta en lugar de duplicarla no es una optimización: el
        índice único parcial del esquema rechaza la segunda inserción, así que duplicar
        sería un error de escritura.
        """
        existing = await self._alerts.find_open_for_commitment(commitment_id)

        if risk_case.consolidated_score >= self._threshold:
            if existing:
                await self._alerts.update(
                    UUID(existing["id"]),
                    {
                        "severity": risk_case.severity.value,
                        "description": risk_case.summary,
                        "risk_case_id": str(risk_case_id),
                    },
                )
                return

            alert_row = await self._alerts.create(
                {
                    "risk_case_id": str(risk_case_id),
                    "commitment_id": str(commitment_id),
                    "severity": risk_case.severity.value,
                    "title": f"Riesgo {risk_case.severity.value} en compromiso",
                    "description": risk_case.summary,
                }
            )
            await self._broadcast(
                EventType.ALERT_CREATED,
                commitment_id=commitment_id,
                risk_case_id=risk_case_id,
                data={
                    "alert_id": alert_row["id"],
                    "severity": risk_case.severity.value,
                    "score": risk_case.consolidated_score,
                },
            )
        elif existing:
            await self._alerts.resolve(UUID(existing["id"]))
            await self._broadcast(
                EventType.ALERT_RESOLVED,
                commitment_id=commitment_id,
                data={"alert_id": existing["id"], "score": risk_case.consolidated_score},
            )

    async def _create_decisions(
        self, outputs: list[AgentOutput], commitment_id: UUID, risk_case_id: UUID
    ) -> None:
        """Crea una ``Decision`` por cada acción que requiere aprobación.

        El backend propone; una persona decide. Nada se ejecuta aquí, y la restricción
        ``check`` del esquema lo respalda: una fila con ``execution_status`` distinto de
        ``not_started`` y sin aprobación no se puede escribir.
        """
        for output in outputs:
            for action in output.recommended_actions:
                if not action.requires_human_approval:
                    continue
                decision_row = await self._decisions.create(
                    {
                        "risk_case_id": str(risk_case_id),
                        "commitment_id": str(commitment_id),
                        "action_type": action.action_type,
                        "title": action.title,
                        "rationale": action.rationale,
                        "proposed_payload": action.payload,
                        "requested_by": output.agent,
                    }
                )
                await self._broadcast(
                    EventType.DECISION_CREATED,
                    commitment_id=commitment_id,
                    risk_case_id=risk_case_id,
                    data={
                        "decision_id": decision_row["id"],
                        "action_type": action.action_type,
                        "title": action.title,
                        "requested_by": output.agent,
                    },
                )

    async def _sync_commitment_status(
        self, risk_case: RiskCase, commitment_id: UUID
    ) -> None:
        """Marca el compromiso en riesgo cuando cruza el umbral.

        Solo sube el estado, nunca lo baja a ``open``: bajarlo requeriría saber que el
        riesgo se mitigó, y eso lo declara una persona al resolver la alerta.
        """
        if risk_case.consolidated_score < self._threshold:
            return
        await self._commitments.set_status(commitment_id, "at_risk")
        await self._broadcast(
            EventType.COMMITMENT_STATUS_CHANGED,
            commitment_id=commitment_id,
            data={"status": "at_risk", "score": risk_case.consolidated_score},
        )

    # --- Difusión ------------------------------------------------------------------

    async def _broadcast(
        self,
        event_type: EventType,
        *,
        commitment_id: UUID | None = None,
        project_id: Any = None,
        risk_case_id: UUID | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Difunde un evento sin dejar que un fallo de difusión rompa el análisis.

        Que nadie escuche, o que el envío falle, no invalida un análisis ya persistido.
        """
        try:
            await self._ws.broadcast(
                WsEvent(
                    type=event_type,
                    commitment_id=commitment_id,
                    project_id=UUID(str(project_id)) if project_id else None,
                    risk_case_id=risk_case_id,
                    data=data or {},
                )
            )
        except Exception as error:  # noqa: BLE001 - la difusión no es crítica
            logger.warning("Difusión fallida para %s: %s", event_type, type(error).__name__)


def _as_datetime(value: Any) -> datetime | None:
    """Convierte a ``datetime`` lo que devuelva PostgREST, o ``None``.

    Tolera la ``Z`` de UTC porque es lo que sale de Supabase, y no eleva ante un valor
    irreconocible: una fecha mal formada es un dato ausente, no un fallo del análisis.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
