"""Servicio de salud.

La comprobación de dependencias nunca eleva: su contrato es informar. Y nunca espera
indefinidamente, porque un health check que se cuelga es peor que uno que informa de un
fallo: los orquestadores lo interpretan como timeout sin saber qué falló (RF-2.3, RF-2.4).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Final

from app.core.config import Settings
from app.core.logging import get_logger
from app.integrations.supabase.client import ping as ping_supabase
from app.schemas.common import (
    DependencyHealth,
    DependencyStatus,
    HealthResponse,
    ServiceStatus,
)

logger = get_logger("health")

#: Presupuesto de la sonda. Deliberadamente más corto que ``HTTP_TIMEOUT_SECONDS``: el
#: health check debe responder rápido incluso cuando la dependencia está agonizando.
DEPENDENCY_PROBE_TIMEOUT_SECONDS: Final[float] = 2.0

SUPABASE_DEPENDENCY: Final[str] = "supabase"


class HealthService:
    """Compone el estado del servicio y de sus dependencias."""

    def __init__(
        self,
        settings: Settings,
        supabase_client: Any | None = None,
        *,
        probe_timeout: float = DEPENDENCY_PROBE_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = settings
        self._supabase_client = supabase_client
        self._probe_timeout = probe_timeout

    async def _probe_supabase(self) -> DependencyHealth:
        """Comprueba Supabase con un presupuesto de tiempo acotado."""
        if self._supabase_client is None:
            return DependencyHealth(
                name=SUPABASE_DEPENDENCY, status=DependencyStatus.UNKNOWN
            )

        started = time.perf_counter()
        try:
            reachable = await asyncio.wait_for(
                ping_supabase(self._supabase_client), timeout=self._probe_timeout
            )
        except TimeoutError:
            logger.warning(
                "La sonda de Supabase agotó %.1fs", self._probe_timeout
            )
            reachable = False
        except Exception as error:  # noqa: BLE001 - informar, no fallar
            logger.warning("La sonda de Supabase falló: %s", type(error).__name__)
            reachable = False

        elapsed_ms = (time.perf_counter() - started) * 1000
        return DependencyHealth(
            name=SUPABASE_DEPENDENCY,
            status=DependencyStatus.UP if reachable else DependencyStatus.DOWN,
            latency_ms=round(elapsed_ms, 2),
        )

    async def check(self) -> HealthResponse:
        """Devuelve el estado del servicio.

        Una dependencia caída degrada el estado pero no impide responder. Una dependencia sin
        comprobar tampoco degrada: no saber no es lo mismo que estar caído.
        """
        dependencies = [await self._probe_supabase()]

        degraded = any(dep.status is DependencyStatus.DOWN for dep in dependencies)
        return HealthResponse(
            status=ServiceStatus.DEGRADED if degraded else ServiceStatus.OK,
            service=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.ENV.value,
            dependencies=dependencies,
        )
