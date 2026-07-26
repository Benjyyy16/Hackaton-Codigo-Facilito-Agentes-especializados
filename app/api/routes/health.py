"""Endpoint de salud."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import HealthServiceDep
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Estado del servicio y de sus dependencias",
    description=(
        "Devuelve 200 tanto si el servicio está sano como si está degradado. "
        "Una dependencia caída se refleja en el campo `status` y en `dependencies`, "
        "no en el código HTTP: así se distingue un proceso muerto de un proceso vivo "
        "con una dependencia caída."
    ),
)
async def get_health(service: HealthServiceDep) -> HealthResponse:
    """Comprueba el servicio y sus dependencias (RF-2)."""
    return await service.check()


@router.get(
    "/ready",
    summary="Readiness probe",
    description=(
        "Devuelve 200 si el servicio puede servir tráfico (almacenamiento conectado). "
        "503 si no está listo. Los balanceadores usan este endpoint para decidir si "
        "enrutar tráfico."
    ),
)
async def readiness(request: Request) -> JSONResponse:
    """200 si puede servir tráfico, 503 si no."""
    storage = getattr(request.app.state, "storage", None)
    if storage is not None and getattr(storage, "is_connected", False):
        return JSONResponse(status_code=status.HTTP_200_OK, content={"ready": True})
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"ready": False, "reason": "storage not connected"},
    )
