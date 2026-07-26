"""Provider de Jira.

Implementa ``EventSourceProvider``. Es la única clase que conoce a la vez el cliente HTTP de
Jira, su mapeador y su validación de webhooks; hacia fuera solo se ve el puerto.

Nada de lo que hay aquí es nuevo: reúne detrás del puerto lo que ya existía en
``integrations/jira``. Esa es la señal de que el puerto es el adecuado, que no obligó a
reescribir la integración.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Mapping
from typing import Any, ClassVar, Final

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.integrations.jira.client import (
    JiraClient,
    close_jira_http_client,
    create_jira_http_client,
)
from app.integrations.jira.mapper import map_issue, map_webhook_payload
from app.integrations.jira.security import (
    WEBHOOK_SECRET_HEADER,
    WEBHOOK_SECRET_QUERY_PARAM,
    verify_webhook_secret,
)
from app.providers.base import EventSink, IngestDecision
from app.schemas.common import DependencyStatus
from app.schemas.events import ExternalEvent, ProviderName
from app.schemas.providers import (
    ProviderCapability,
    ProviderHealth,
    ProviderKind,
    SyncReport,
    SyncRequest,
)

logger = get_logger("provider.jira")

#: Presupuesto de la comprobación de salud. Corto a propósito: el health check debe responder
#: rápido incluso con Jira agonizando.
HEALTH_TIMEOUT_SECONDS: Final[float] = 3.0


def build_project_jql(project_key: str) -> str:
    """Construye la consulta por defecto para un proyecto (RF-4.2).

    Ordena por ``updated`` descendente para que, si la recogida se corta por un límite, lo
    traído sea lo más reciente y por tanto lo más relevante.

    La clave se interpola entre comillas y con las comillas internas escapadas, para que un
    valor inesperado no pueda alterar la estructura de la consulta.
    """
    safe_key = project_key.replace('"', '\\"')
    return f'project = "{safe_key}" ORDER BY updated DESC'


class JiraProvider:
    """Jira Cloud como fuente de eventos."""

    name: ClassVar[ProviderName] = ProviderName.JIRA
    kind: ClassVar[ProviderKind] = ProviderKind.EVENT_SOURCE
    capabilities: ClassVar[frozenset[ProviderCapability]] = frozenset(
        {ProviderCapability.SYNC, ProviderCapability.WEBHOOK}
    )

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
        self._http: httpx.AsyncClient | None = None
        self._client: JiraClient | None = None

    # --- Ciclo de vida ------------------------------------------------------------

    async def connect(self) -> None:
        """Crea el cliente HTTP de vida larga. Es idempotente."""
        if self._http is not None:
            return
        self._http = create_jira_http_client(self._settings, transport=self._transport)
        self._client = JiraClient(
            self._http, max_retries=self._settings.HTTP_MAX_RETRIES
        )
        logger.info("Provider de Jira conectado")

    async def close(self) -> None:
        await close_jira_http_client(self._http)
        self._http = None
        self._client = None

    async def health(self) -> ProviderHealth:
        """Comprueba que Jira responde. No eleva: informa (RF-2.3)."""
        if self._client is None:
            return ProviderHealth(
                provider=self.name.value,
                status=DependencyStatus.UNKNOWN,
                detail="El provider no está conectado.",
            )

        started = time.perf_counter()
        try:
            # ``/myself`` es la sonda más barata que además valida las credenciales.
            await self._client.get_current_user(timeout=HEALTH_TIMEOUT_SECONDS)
            status = DependencyStatus.UP
            detail = None
        except Exception as error:  # noqa: BLE001 - informar, no fallar
            status = DependencyStatus.DOWN
            detail = type(error).__name__
            logger.warning("Jira no responde: %s", detail)

        return ProviderHealth(
            provider=self.name.value,
            status=status,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
            detail=detail,
        )

    # --- Webhooks -----------------------------------------------------------------

    def verify_webhook(
        self, headers: Mapping[str, str], params: Mapping[str, str]
    ) -> None:
        """Valida el secreto compartido (RF-5.2).

        Jira Cloud no firma los webhooks, así que no hay firma que comprobar. El secreto llega
        por cabecera o por parámetro de consulta, según lo que permita el formulario de
        registro del webhook.
        """
        verify_webhook_secret(
            self._settings.JIRA_WEBHOOK_SECRET,
            header_value=headers.get(WEBHOOK_SECRET_HEADER)
            or headers.get(WEBHOOK_SECRET_HEADER.lower()),
            query_value=params.get(WEBHOOK_SECRET_QUERY_PARAM),
        )

    def parse_webhook(self, payload: Mapping[str, Any]) -> ExternalEvent:
        return map_webhook_payload(dict(payload), base_url=self._settings.JIRA_BASE_URL)

    # --- Lectura ------------------------------------------------------------------

    def _require_client(self) -> JiraClient:
        if self._client is None:
            raise RuntimeError(
                "El provider de Jira no está conectado; falta llamar a connect()."
            )
        return self._client

    def resolve_query(self, request: SyncRequest) -> str:
        """Devuelve la consulta a ejecutar: la pedida, o la construida por defecto."""
        return request.query or build_project_jql(request.workspace_key)

    async def ensure_workspace_exists(self, workspace_key: str) -> None:
        """Comprueba que el proyecto existe en Jira.

        Eleva ``JiraNotFoundError``, que se traduce a ``404``. Sin esta comprobación, una clave
        equivocada daría una sincronización vacía silenciosa (RF-4.6).
        """
        await self._require_client().get_project(workspace_key)

    async def fetch_events(self, request: SyncRequest) -> AsyncIterator[ExternalEvent]:
        """Itera los eventos del proyecto, sin persistir.

        La paginación queda encapsulada en el cliente: quien consume no sabe cómo se pagina
        (RF-4.3).
        """
        client = self._require_client()
        query = self.resolve_query(request)

        async for issue in client.iter_issues(query, max_issues=request.max_items):
            yield map_issue(issue, base_url=self._settings.JIRA_BASE_URL)

    async def sync(self, request: SyncRequest, sink: EventSink) -> SyncReport:
        """Recorre el proyecto y entrega cada evento al sumidero (RF-4.5).

        El provider dirige el recorrido porque solo él sabe paginar y respetar los límites de
        tasa de Jira, pero no toca la base de datos: quien persiste es el sumidero. Así la
        integración no queda acoplada al almacenamiento.

        Un elemento que falla se cuenta y no aborta la carga: abortar dejaría el proyecto a
        medio cargar por un solo registro defectuoso.
        """
        await self.ensure_workspace_exists(request.workspace_key)
        query = self.resolve_query(request)

        processed = created = skipped = failed = 0

        async for event in self.fetch_events(request):
            processed += 1
            try:
                decision = await sink(event)
            except Exception as error:  # noqa: BLE001 - un elemento roto no aborta
                failed += 1
                logger.warning(
                    "El evento %s no se pudo ingerir: %s",
                    event.external_key,
                    type(error).__name__,
                )
                continue

            if decision is IngestDecision.CREATED:
                created += 1
            elif decision is IngestDecision.DUPLICATE:
                skipped += 1
            else:
                failed += 1

        logger.info(
            "Sincronización de %s: %d procesados, %d creados, %d omitidos, %d fallidos",
            request.workspace_key,
            processed,
            created,
            skipped,
            failed,
        )

        return SyncReport(
            provider=self.name,
            workspace_key=request.workspace_key,
            query=query,
            processed=processed,
            created=created,
            skipped=skipped,
            failed=failed,
            truncated=request.max_items is not None and processed >= request.max_items,
        )
