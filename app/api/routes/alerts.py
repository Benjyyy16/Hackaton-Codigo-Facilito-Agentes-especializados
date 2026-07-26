"""Rutas de alertas."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DomainRepositoriesDep
from app.schemas.domain import AlertAcknowledge, AlertRead

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get(
    "",
    response_model=list[AlertRead],
    summary="Listar alertas",
    description="Lista paginada de alertas con filtro opcional por status y severity.",
)
async def list_alerts(
    repos: DomainRepositoriesDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
) -> list[AlertRead]:
    filters: dict[str, str] = {}
    if status_filter:
        filters["status"] = status_filter
    if severity:
        filters["severity"] = severity
    page = await repos.alerts.list_page(limit=limit, offset=offset, filters=filters)
    return [AlertRead.model_validate(row) for row in page.items]


@router.patch(
    "/{alert_id}/acknowledge",
    response_model=AlertRead,
    summary="Reconocer alerta",
    description="Marca una alerta como reconocida por un usuario.",
)
async def acknowledge_alert(
    alert_id: UUID,
    body: AlertAcknowledge,
    repos: DomainRepositoriesDep,
) -> AlertRead:
    # get_or_raise valida existencia; acknowledge actualiza estado
    await repos.alerts.get_or_raise(alert_id)
    row = await repos.alerts.acknowledge(alert_id, body.acknowledged_by)
    return AlertRead.model_validate(row)
