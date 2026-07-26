"""Contrato de los agentes.

Un agente es una función de datos a datos: recibe un contexto, devuelve un resultado. Sin
``async``, sin E/S, sin importar FastAPI ni el cliente de Supabase (RF-8.3).

Esa pobreza deliberada es lo que hace que sean la capa más barata de probar y la más fácil de
sustituir: cambiar un agente determinístico por uno que llame a un LLM significa escribir una
clase nueva que cumpla este protocolo, sin tocar ningún servicio (RF-8.4).

El contexto lleva ``ExternalEvent``, que es agnóstico del provider. Un agente que necesitara
saber si el evento vino de Jira o de GitHub sería la señal de que la arquitectura de providers
falló.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import (
    AgentOutcome,
    CommitmentSnapshot,
    ProjectSnapshot,
    Signal,
)
from app.schemas.events import ExternalEvent


class AgentContext(BaseModel):
    """Todo lo que un agente necesita para decidir.

    ``now`` viaja en el contexto en lugar de leerse del reloj dentro del agente. Es lo que hace
    que los casos de vencimiento sean deterministas y que un test no tenga que parchear
    ``datetime`` (RF-8.7).
    """

    model_config = ConfigDict(frozen=True)

    event: ExternalEvent = Field(description="Evento que dispara el análisis.")
    now: datetime = Field(description="Instante de referencia del análisis.")
    commitment: CommitmentSnapshot | None = Field(
        default=None, description="Compromiso asociado, si ya existe."
    )
    project: ProjectSnapshot | None = Field(
        default=None, description="Contenedor al que pertenece el evento."
    )
    #: Eventos recientes del mismo elemento, del más reciente al más antiguo. Alimenta las
    #: señales que solo se ven en el histórico, como el estancamiento.
    recent_events: list[ExternalEvent] = Field(
        default_factory=list, description="Historial reciente del elemento."
    )


@runtime_checkable
class Agent(Protocol):
    """Agente de análisis.

    Deliberadamente sincrónico: un agente con E/S dejaría de ser puro y arrastraría al resto a
    necesitar dobles para probarlo.
    """

    name: str

    def run(self, context: AgentContext) -> AgentOutcome:
        """Analiza el contexto y devuelve su contribución al riesgo."""
        ...


class BaseAgent:
    """Ayudas comunes a los agentes determinísticos.

    No es obligatorio heredar de aquí: basta con cumplir el protocolo. Existe solo para no
    repetir la composición del resultado en cada agente.
    """

    name: str = "agent"

    def run(self, context: AgentContext) -> AgentOutcome:  # pragma: no cover - abstracta
        raise NotImplementedError

    def _outcome(
        self,
        signals: list[Signal],
        *,
        detail: dict[str, object] | None = None,
    ) -> AgentOutcome:
        """Compone el resultado a partir de los hallazgos.

        La puntuación del agente es el mayor de los pesos, no su suma. Sumar haría que tres
        señales leves pesaran más que una grave, y que acumular hallazgos menores saturara la
        escala hasta 100 sin que nada grave hubiera ocurrido.
        """
        score = max((signal.weight for signal in signals), default=0)
        return AgentOutcome(
            agent=self.name,
            score=min(score, 100),
            signals=signals,
            detail=detail or {},
        )
