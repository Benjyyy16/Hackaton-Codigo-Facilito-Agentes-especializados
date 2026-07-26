"""Rutas genéricas de providers.

Ninguna rama por provider. El nombre llega en la ruta, el registro lo resuelve y el puerto hace
el resto: añadir GitHub o Notion no toca este archivo. Ese es el criterio de aceptación de la
arquitectura de providers.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, Path, Request, status

from app.api.deps import (
    OrchestratorServiceDep,
    PostIngestHookDep,
    PrincipalDep,
    ProviderRegistryDep,
)
from app.core.exceptions import ErrorResponse
from app.core.logging import get_logger
from app.integrations.jira.security import JIRA_DELIVERY_HEADER
from app.schemas.events import ProviderName
from app.schemas.jira import WebhookAck
from app.schemas.providers import ProviderInfo, SyncReport, SyncRequest

logger = get_logger("api.providers")

router = APIRouter(tags=["providers"])

ProviderPath = Annotated[
    ProviderName,
    Path(description="Provider al que va dirigida la operación."),
]


@router.get(
    "/providers",
    response_model=list[ProviderInfo],
    summary="Providers registrados y su estado",
    description=(
        "Devuelve solo los providers **configurados** en esta instancia. Un provider sin "
        "credenciales no se registra, en lugar de aparecer y fallar al usarlo."
    ),
)
async def list_providers(registry: ProviderRegistryDep) -> list[ProviderInfo]:
    """Describe los providers disponibles (RF-2, apoyo operativo)."""
    return await registry.describe()


@router.post(
    "/webhooks/{provider}",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Recibe un evento de un provider",
    description=(
        "Valida la autenticidad según el mecanismo del provider, traduce el payload al evento "
        "del dominio, lo deduplica y lo persiste. El análisis se ejecuta en segundo plano para "
        "que la respuesta sea rápida.\n\n"
        "Cada provider valida a su manera: Jira Cloud no firma y usa un secreto compartido, "
        "otros firman con HMAC. La ruta no conoce esa diferencia.\n\n"
        "Códigos: `200` aceptado o duplicado, `202` evento no soportado, `401` autenticación "
        "inválida, `404` provider no configurado."
    ),
    responses={
        status.HTTP_202_ACCEPTED: {
            "model": WebhookAck,
            "description": "Evento recibido pero descartado por no estar soportado.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Autenticación de la entrega inválida o ausente.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "El provider no está configurado en esta instancia.",
        },
    },
)
async def receive_webhook(
    provider: ProviderPath,
    request: Request,
    orchestrator: OrchestratorServiceDep,
    post_ingest: PostIngestHookDep,
    background_tasks: BackgroundTasks,
    payload: Annotated[dict[str, Any], Body(description="Payload original del provider.")],
) -> WebhookAck:
    """Ingiere un evento entregado por un provider (RF-5)."""
    delivery_id = request.headers.get(JIRA_DELIVERY_HEADER)
    if delivery_id:
        logger.info("Entrega %s de %s", delivery_id, provider.value)

    outcome = await orchestrator.handle_webhook(
        provider,
        payload,
        dict(request.headers),
        dict(request.query_params),
    )

    if outcome.duplicated:
        return WebhookAck(
            accepted=True,
            duplicated=True,
            event_id=str(outcome.event_id) if outcome.event_id else None,
            detail="El evento ya había sido registrado.",
        )

    # Fuera del ciclo de petición y respuesta: un análisis lento no debe retrasar la respuesta,
    # porque los providers reintentan si tarda (RF-5.7).
    background_tasks.add_task(post_ingest, outcome)

    return WebhookAck(
        accepted=True,
        duplicated=False,
        event_id=str(outcome.event_id) if outcome.event_id else None,
    )


@router.post(
    "/providers/{provider}/sync",
    response_model=SyncReport,
    status_code=status.HTTP_200_OK,
    summary="Sincroniza un contenedor a través de un provider",
    description=(
        "Carga el estado actual para tener una base sobre la que detectar cambios. Los cambios "
        "posteriores llegan por webhook, no por sondeo.\n\n"
        "La operación es idempotente: repetirla sin cambios en el origen no crea eventos nuevos."
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "El provider no está configurado o el contenedor no existe.",
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": "El provider no está disponible o rechazó las credenciales.",
        },
    },
)
async def sync_provider(
    provider: ProviderPath,
    payload: SyncRequest,
    orchestrator: OrchestratorServiceDep,
    _principal: PrincipalDep,
) -> SyncReport:
    """Ejecuta la sincronización de un contenedor (RF-4)."""
    return await orchestrator.sync(provider, payload)
