"""Recepción de webhooks de Jira."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, Header, Query, status

from app.api.deps import PostIngestHookDep, SettingsDep, WebhookServiceDep
from app.core.exceptions import ErrorResponse
from app.core.logging import get_logger
from app.integrations.jira.security import (
    JIRA_DELIVERY_HEADER,
    WEBHOOK_SECRET_HEADER,
    WEBHOOK_SECRET_QUERY_PARAM,
    verify_webhook_secret,
)
from app.schemas.jira import WebhookAck

logger = get_logger("api.webhooks")

router = APIRouter(tags=["webhooks"])


@router.post(
    "/webhooks/jira",
    response_model=WebhookAck,
    status_code=status.HTTP_200_OK,
    summary="Recibe un evento de Jira",
    description=(
        "Valida el secreto compartido, normaliza el evento, lo deduplica y lo persiste. "
        "El análisis se ejecuta en segundo plano para que la respuesta a Jira sea rápida.\n\n"
        "El secreto se acepta en la cabecera `X-Hook-Secret` o en el parámetro `secret`, "
        "porque Jira Cloud no firma los webhooks y en algunos formularios solo se puede "
        "configurar la URL.\n\n"
        "Códigos: `200` aceptado o duplicado, `202` tipo de evento no soportado, "
        "`401` secreto inválido."
    ),
    responses={
        status.HTTP_202_ACCEPTED: {
            "model": WebhookAck,
            "description": "Evento recibido pero descartado por no estar soportado.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Secreto compartido inválido o ausente.",
        },
    },
)
async def receive_jira_webhook(
    settings: SettingsDep,
    service: WebhookServiceDep,
    post_ingest: PostIngestHookDep,
    background_tasks: BackgroundTasks,
    payload: Annotated[dict[str, Any], Body(description="Payload original de Jira.")],
    secret_header: Annotated[
        str | None,
        Header(alias=WEBHOOK_SECRET_HEADER, description="Secreto compartido."),
    ] = None,
    secret_query: Annotated[
        str | None,
        Query(alias=WEBHOOK_SECRET_QUERY_PARAM, description="Secreto compartido."),
    ] = None,
    delivery_id: Annotated[
        str | None,
        Header(alias=JIRA_DELIVERY_HEADER, description="Identificador de entrega de Jira."),
    ] = None,
) -> WebhookAck:
    """Ingiere un evento de Jira (RF-5).

    La validación del secreto va primero: un payload no autenticado no debe llegar a
    persistirse ni a procesarse (RF-5.2).
    """
    verify_webhook_secret(
        settings.JIRA_WEBHOOK_SECRET,
        header_value=secret_header,
        query_value=secret_query,
    )

    if delivery_id:
        logger.info("Entrega de Jira %s", delivery_id)

    outcome = await service.ingest_payload(payload)

    if outcome.duplicated:
        return WebhookAck(
            accepted=True,
            duplicated=True,
            event_id=str(outcome.event_id) if outcome.event_id else None,
            detail="El evento ya había sido registrado.",
        )

    # El análisis se registra como tarea en segundo plano para no retrasar la respuesta a
    # Jira, que reintenta si tarda (RF-5.7).
    background_tasks.add_task(post_ingest, outcome)

    return WebhookAck(
        accepted=True,
        duplicated=False,
        event_id=str(outcome.event_id) if outcome.event_id else None,
    )
