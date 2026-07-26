"""Puertos de los providers.

Este módulo define **la única forma** en que la lógica de negocio habla con un sistema externo.
Ningún servicio y ningún agente importa un provider concreto: dependen de estos protocolos.

Sobre la segregación en tres puertos, que se aparta de la idea de una única interfaz para todo:
Supabase no es una fuente de eventos, es el almacén donde se guardan. ``sync()`` y
``fetch_events()`` no significan nada para él, así que solo podría implementarlos devolviendo
vacío o lanzando "no soportado". Eso rompe la segregación de interfaces y la sustitución de
Liskov. La salida es un puerto base con lo que de verdad comparten, el ciclo de vida, y dos
puertos que lo extienden con lo propio de cada papel.

Los cinco providers de integración sí implementan ``connect``, ``sync``, ``fetch_events`` y
``health``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from app.repositories.alerts import AlertRepository
from app.repositories.commitments import CommitmentRepository
from app.repositories.events import EventRepository
from app.repositories.risk_analyses import RiskAnalysisRepository
from app.repositories.workspaces import WorkspaceRepository
from app.schemas.events import ExternalEvent, ProviderName
from app.schemas.providers import (
    ProviderCapability,
    ProviderHealth,
    ProviderKind,
    SyncReport,
    SyncRequest,
)


@runtime_checkable
class Provider(Protocol):
    """Ciclo de vida común a todo provider."""

    name: ProviderName
    kind: ProviderKind

    async def connect(self) -> None:
        """Prepara los recursos del provider.

        Se invoca una vez en el arranque. Debe ser idempotente: llamarla dos veces no debe
        duplicar conexiones.
        """
        ...

    async def health(self) -> ProviderHealth:
        """Comprueba el estado del provider.

        **No debe elevar.** Su contrato es informar, y quien la consume es el health check
        (RF-2.3).
        """
        ...

    async def close(self) -> None:
        """Libera los recursos. Un fallo al cerrar se registra, no se propaga."""
        ...


class IngestDecision(StrEnum):
    """Qué pasó con un evento que el provider entregó al sumidero."""

    CREATED = "created"
    DUPLICATE = "duplicate"
    FAILED = "failed"


#: Función que recibe un evento y lo persiste, devolviendo qué hizo con él.
#:
#: Es una inversión de dependencia deliberada: el provider dirige el recorrido, porque solo él
#: sabe paginar y respetar los límites de tasa de su servicio, pero no sabe nada de
#: persistencia. Sin este sumidero, ``sync()`` solo podría contar lo recorrido y quedaría tan
#: hueco como los métodos que se le quitaron al provider de almacenamiento.
EventSink = Callable[[ExternalEvent], Awaitable[IngestDecision]]


@runtime_checkable
class EventSourceProvider(Provider, Protocol):
    """Provider que aporta eventos: Jira, GitHub, Notion, AWS, Rightway."""

    capabilities: frozenset[ProviderCapability]

    async def sync(self, request: SyncRequest, sink: EventSink) -> SyncReport:
        """Recorre el estado actual del contenedor y entrega cada evento al sumidero.

        Es la carga inicial, a demanda. No es un sondeo periódico: los cambios posteriores
        llegan por webhook (RF-12.7).
        """
        ...

    def fetch_events(self, request: SyncRequest) -> AsyncIterator[ExternalEvent]:
        """Itera los eventos del contenedor, sin persistir.

        Devuelve un iterador asíncrono porque el volumen puede ser grande y la paginación es
        asunto del provider: quien consume no debe saber cómo se pagina.
        """
        ...

    def verify_webhook(
        self, headers: Mapping[str, str], params: Mapping[str, str]
    ) -> None:
        """Comprueba la autenticidad de una entrega y eleva si no es válida.

        Vive en el puerto porque cada servicio autentica distinto: Jira Cloud no firma y usa un
        secreto compartido, GitHub firma con HMAC SHA-256 en ``X-Hub-Signature-256``, Notion
        tiene su propio esquema. Si esto viviera en la ruta, la ruta necesitaría una rama por
        provider, que es exactamente lo que la arquitectura quiere eliminar.
        """
        ...

    def parse_webhook(self, payload: Mapping[str, object]) -> ExternalEvent:
        """Traduce el payload de una entrega al evento del dominio.

        Eleva ``UnsupportedEventError`` cuando el tipo de evento no interesa, que la ruta
        traduce a ``202`` y descarta de forma explícita (RF-5.4).
        """
        ...


@runtime_checkable
class StorageProvider(Provider, Protocol):
    """Provider de persistencia: Supabase.

    No expone ``sync`` ni ``fetch_events`` a propósito. Lo que ofrece es acceso a los
    repositorios, que son la única puerta a los datos (RF-7.2).
    """

    def repositories(self) -> RepositoryBundle:
        """Devuelve los repositorios respaldados por este almacén."""
        ...


@dataclass(frozen=True)
class RepositoryBundle:
    """Repositorios que un ``StorageProvider`` proporciona.

    Los repositorios son abstracciones del dominio sobre el almacén, no detalles del provider,
    así que aquí se tipan de verdad. Lo que queda oculto es qué almacén los respalda.
    """

    workspaces: WorkspaceRepository
    events: EventRepository
    commitments: CommitmentRepository
    analyses: RiskAnalysisRepository
    alerts: AlertRepository
