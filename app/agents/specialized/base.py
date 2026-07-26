"""Contrato de los agentes especializados de Datgent.

Un agente recibe un ``AgentContext`` y devuelve un ``AgentOutput``. Sin ``async``, sin
E/S, sin red, sin base de datos: los datos externos ya vienen recolectados en el
contexto.

Esa pobreza deliberada tiene dos consecuencias que importan. La primera es que un
agente se prueba sin levantar nada. La segunda es que sustituir un agente
determinístico por uno respaldado por un LLM significa escribir una clase nueva que
cumpla este protocolo, sin tocar ningún servicio.

Todos los agentes analizan el MISMO ``Commitment``. Es lo que permite correlacionar
después: si cada uno mirara su propia entidad, el orquestador no tendría nada que
cruzar y Datgent sería cuatro herramientas en un mismo despliegue.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.domain import (
    AgentOutput,
    AgentRunStatus,
    CommitmentSnapshot,
    Evidence,
    Finding,
    ProjectSnapshot,
    RetrievedChunk,
    Severity,
    severity_for_score,
)


class AgentContext(BaseModel):
    """Todo lo que un agente necesita para decidir, ya recolectado.

    ``now`` viaja en el contexto en lugar de leerse del reloj dentro del agente. Es lo
    que hace deterministas los casos de vencimiento y lo que permite que un test no
    tenga que parchear ``datetime``.

    Congelado: un agente no puede alterar el contexto que otro va a leer. Sin eso, el
    orden de ejecución cambiaría los resultados y la correlación dejaría de ser
    reproducible.
    """

    model_config = ConfigDict(frozen=True)

    commitment: CommitmentSnapshot
    project: ProjectSnapshot | None = None
    now: datetime

    #: Señales por proveedor, ya normalizadas. La clave es el nombre del provider.
    #: Un agente lee solo la suya: el agente de Jira no debe saber qué hay en la de
    #: GitHub, porque entonces la separación no serviría para nada.
    signals: dict[str, Any] = Field(default_factory=dict)

    #: Eventos recientes del compromiso, del más nuevo al más antiguo. Alimenta las
    #: señales que solo existen en el histórico, como el estancamiento.
    recent_events: list[dict[str, Any]] = Field(default_factory=list)

    #: Fragmentos documentales recuperados por el RAG. Aportan contexto contractual
    #: (un SLA, una cláusula de penalización) que no está en ningún provider.
    documents: list[RetrievedChunk] = Field(default_factory=list)

    def signal(self, provider: str) -> dict[str, Any]:
        """Señales de un proveedor, o un diccionario vacío si no hay.

        Devuelve vacío en lugar de elevar porque un provider sin configurar es un caso
        normal, no un error: el agente debe poder reportar "no tengo datos" en
        ``missing_information``.
        """
        value = self.signals.get(provider)
        return value if isinstance(value, dict) else {}


@runtime_checkable
class SpecializedAgent(Protocol):
    """Agente de análisis especializado en un dominio."""

    name: str

    def analyze(self, context: AgentContext) -> AgentOutput:
        """Analiza el compromiso desde su especialidad."""
        ...


class BaseSpecializedAgent:
    """Ayudas comunes a los agentes determinísticos.

    No es obligatorio heredar: basta con cumplir el protocolo. Existe para no repetir
    la composición del resultado en cada agente, que es donde se cuelan las
    inconsistencias.
    """

    name: str = "agent"
    #: Familia de los hallazgos que produce este agente.
    category: str = "general"

    def analyze(self, context: AgentContext) -> AgentOutput:  # pragma: no cover
        raise NotImplementedError

    # --- Composición del resultado -------------------------------------------------

    @staticmethod
    def _evidence(
        *,
        source_type: str,
        provider: str,
        explanation: str,
        observed_at: datetime,
        field: str | None = None,
        value: Any = None,
        external_id: str | None = None,
        source_url: str | None = None,
        content: str | None = None,
    ) -> Evidence:
        """Construye una evidencia normalizando el valor a texto.

        El valor se guarda como texto y no con su tipo original a propósito: la
        evidencia es un registro de lo observado, no un dato para recalcular. Que
        ``assignee`` fuera ``None`` se lee igual de bien como ``"None"``, y así la
        columna admite cualquier campo de cualquier provider.
        """
        return Evidence(
            source_type=source_type,  # type: ignore[arg-type]
            provider=provider,
            external_id=external_id,
            source_url=source_url,
            field=field,
            value=None if value is None else str(value),
            content=content,
            observed_at=observed_at,
            explanation=explanation,
        )

    def _finding(
        self,
        *,
        code: str,
        summary: str,
        risk_score: int,
        confidence: float = 1.0,
        impact: str | None = None,
        evidence: list[Evidence] | None = None,
        category: str | None = None,
    ) -> Finding:
        """Compone un hallazgo derivando la severidad de la puntuación.

        La severidad no se pasa como parámetro: se deriva. Dejarla libre permitiría un
        hallazgo con ``risk_score=10`` y ``severity=critical``, y a partir de ahí
        ninguna agregación tendría sentido.
        """
        return Finding(
            category=category or self.category,
            code=code,
            severity=severity_for_score(risk_score),
            risk_score=risk_score,
            confidence=confidence,
            summary=summary,
            impact=impact,
            evidence=evidence or [],
        )

    def _output(
        self,
        context: AgentContext,
        findings: list[Finding],
        *,
        summary: str = "",
        missing_information: list[str] | None = None,
        recommended_actions: list[Any] | None = None,
        evidence: list[Evidence] | None = None,
    ) -> AgentOutput:
        """Compone la salida del agente a partir de sus hallazgos.

        La puntuación del agente es el MÁXIMO de sus hallazgos, no la suma. Sumar haría
        que tres señales leves pesaran más que una grave, y que acumular hallazgos
        menores saturase la escala hasta 100 sin que nada grave hubiera ocurrido.

        La confianza es la MEDIA de las de sus hallazgos, ponderada por riesgo: la
        confianza del agente debe parecerse a la del hallazgo que domina su
        puntuación, no a la del más especulativo.
        """
        score = max((f.risk_score for f in findings), default=0)
        confidence = self._weighted_confidence(findings)

        requires_approval = any(
            getattr(action, "requires_human_approval", True)
            for action in (recommended_actions or [])
        )

        return AgentOutput(
            agent=self.name,
            commitment_id=context.commitment.id,
            status=AgentRunStatus.COMPLETED,
            risk_score=min(score, 100),
            severity=severity_for_score(score),
            confidence=confidence,
            summary=summary or self._default_summary(findings),
            findings=findings,
            evidence=evidence or [],
            missing_information=missing_information or [],
            recommended_actions=recommended_actions or [],
            requires_human_approval=requires_approval,
        )

    @staticmethod
    def _weighted_confidence(findings: list[Finding]) -> float:
        """Confianza del agente: media ponderada por riesgo de sus hallazgos.

        Sin hallazgos la confianza es 1.0: afirmar "no encontré nada" con los datos
        disponibles es una afirmación sólida. Lo que sería débil es afirmarlo sin
        datos, y eso se expresa en ``missing_information``, no aquí.
        """
        if not findings:
            return 1.0
        total_weight = sum(f.risk_score for f in findings)
        if total_weight == 0:
            return round(sum(f.confidence for f in findings) / len(findings), 2)
        weighted = sum(f.confidence * f.risk_score for f in findings)
        return round(weighted / total_weight, 2)

    def _default_summary(self, findings: list[Finding]) -> str:
        if not findings:
            return f"{self.name}: sin señales de riesgo con los datos disponibles."
        worst = max(findings, key=lambda f: f.risk_score)
        extra = f" (+{len(findings) - 1} más)" if len(findings) > 1 else ""
        return f"{worst.summary}{extra}"

    def _empty_output(
        self, context: AgentContext, missing: list[str], *, reason: str
    ) -> AgentOutput:
        """Salida cuando el agente no tiene datos para concluir.

        Devolver riesgo 0 con confianza 0 y el hueco declarado, en lugar de riesgo 0 con
        confianza 1, es la diferencia entre "no hay problema" y "no puedo saberlo". El
        orquestador necesita distinguirlos para no dar por seguro un compromiso que
        nadie pudo revisar.
        """
        return AgentOutput(
            agent=self.name,
            commitment_id=context.commitment.id,
            status=AgentRunStatus.SKIPPED,
            risk_score=0,
            severity=Severity.LOW,
            confidence=0.0,
            summary=reason,
            missing_information=missing,
        )
