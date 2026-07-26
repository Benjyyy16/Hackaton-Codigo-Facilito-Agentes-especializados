"""Rutas del caso demo.

SEGURIDAD: estas rutas SOLO responden si DEMO_MODE_ENABLED=true o ENV in (development, test).
En production sin la bandera → 404 (no 403: no revelar que la ruta existe).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.api.deps import AnalysisServiceDep, DomainRepositoriesDep, SettingsDep
from app.core.config import Environment, Settings
from app.services.demo_service import DEMO_COMMITMENT_ID, DemoService

router = APIRouter(prefix="/demo", tags=["demo"])


def _check_demo_access(settings: Settings) -> None:
    """Verifica que el entorno permite rutas demo. 404 si no."""
    allowed = (
        settings.DEMO_MODE_ENABLED
        or settings.ENV in (Environment.DEVELOPMENT, Environment.TEST)
    )
    if not allowed:
        # 404, no 403: no revelar que la ruta existe en producción
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def _demo_service(repos: DomainRepositoriesDep) -> DemoService:
    return DemoService(
        projects=repos.projects,
        commitments=repos.commitments,
        source_events=repos.source_events,
        documents=repos.documents,
    )


@router.post(
    "/seed",
    status_code=status.HTTP_201_CREATED,
    summary="Crear datos del caso demo",
)
async def seed_demo(
    repos: DomainRepositoriesDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    _check_demo_access(settings)
    svc = _demo_service(repos)
    return await svc.seed()


@router.post(
    "/simulate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Simular análisis del caso demo",
    description="Inyecta señales y dispara el análisis en background.",
)
async def simulate_demo(
    repos: DomainRepositoriesDep,
    analysis: AnalysisServiceDep,
    settings: SettingsDep,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    _check_demo_access(settings)
    svc = _demo_service(repos)

    # Asegurar que los datos existen
    await svc.seed()

    # Obtener señales completas
    signals = await svc.get_signals()

    # Disparar análisis en background
    background_tasks.add_task(
        analysis.analyze_commitment,
        DEMO_COMMITMENT_ID,
        signals=signals,
    )

    return {
        "status": "analysis_triggered",
        "commitment_id": str(DEMO_COMMITMENT_ID),
        "message": "Análisis disparado en background. Consultar /risk-cases o WebSocket para resultados.",
    }


@router.delete(
    "/reset",
    status_code=status.HTTP_200_OK,
    summary="Limpiar datos del caso demo",
)
async def reset_demo(
    repos: DomainRepositoriesDep,
    settings: SettingsDep,
) -> dict[str, str]:
    _check_demo_access(settings)
    svc = _demo_service(repos)
    return await svc.reset()
