"""Servicio de salud.

La comprobación de dependencias nunca eleva: su contrato es informar. Y nunca espera
indefinidamente, porque un health check que se cuelga es peor que uno que informa de un fallo:
los orquestadores lo interpretan como timeout sin saber qué falló (RF-2.3, RF-2.4).

Informa del almacén y de cada provider registrado. Los providers no configurados no aparecen: no
están registrados, así que no hay nada que inventar sobre ellos.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Final

from app.core.config import Settings
from app.core.logging import get_logger
from app.integrations.supabase.client import ping as ping_supabase
from app.providers.registry import ProviderRegistry
from app.schemas.common import (
    DependencyHealth,
    DependencyStatus,
    HealthResponse,
    ServiceStatus,
)

logger = get_logger("health")

#: Presupuesto de la sonda. Deliberadamente más corto que ``HTTP_TIMEOUT_SECONDS``: el health
#: check debe responder rápido incluso cuando la dependencia está agonizando.
DEPENDENCY_PROBE_TIMEOUT_SECONDS: Final[float] = 2.0

STORAGE_DEPENDENCY: Final[str] = "supabase"


class HealthService:
    """Compone el estado del servicio, del almacén y de los providers."""

    def __init__(
        self,
        settings: Settings,
        storage_client: Any | None = None,
        *,
        registry: ProviderRegistry | None = None,
        probe_timeout: float = DEPENDENCY_PROBE_TIMEOUT_SECONDS,
    ) -> None:
        self._settings = settings
        self._storage_client = storage_client
        self._registry = registry
        self._probe_timeout = probe_timeout

    async def _probe_storage(self) -> DependencyHealth:
        """Comprueba el almacén con un presupuesto de tiempo acotado."""
        if self._storage_client is None:
            return DependencyHealth(
                name=STORAGE_DEPENDENCY, status=DependencyStatus.UNKNOWN
            )

        started = time.perf_counter()
        try:
            reachable = await asyncio.wait_for(
                ping_supabase(self._storage_client), timeout=self._probe_timeout
            )
        except TimeoutError:
            logger.warning("La sonda de Supabase agotó %.1fs", self._probe_timeout)
            reachable = False
        except Exception as error:  # noqa: BLE001 - informar, no fallar
            logger.warning("La sonda de Supabase falló: %s", type(error).__name__)
            reachable = False

        return DependencyHealth(
            name=STORAGE_DEPENDENCY,
            status=DependencyStatus.UP if reachable else DependencyStatus.DOWN,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    async def _probe_providers(self) -> list[DependencyHealth]:
        """Comprueba los providers registrados.

        El registro los sondea en paralelo y absorbe sus fallos, así que aquí solo hay que
        traducir el resultado.
        """
        if self._registry is None or len(self._registry) == 0:
            return []

        try:
            healths = await asyncio.wait_for(
                self._registry.health_all(), timeout=self._probe_timeout
            )
        except TimeoutError:
            logger.warning("La sonda de providers agotó %.1fs", self._probe_timeout)
            return [
                DependencyHealth(name=name.value, status=DependencyStatus.DOWN)
                for name in self._registry.names()
            ]

        return [
            DependencyHealth(
                name=health.provider,
                status=health.status,
                latency_ms=health.latency_ms,
            )
            for health in healths
        ]

    async def check(self) -> HealthResponse:
        """Devuelve el estado del servicio.

        Una dependencia caída degrada pero no impide responder. Una dependencia sin comprobar no
        degrada: no saber no es lo mismo que estar caído.
        """
        dependencies = [await self._probe_storage(), *await self._probe_providers()]

        degraded = any(dep.status is DependencyStatus.DOWN for dep in dependencies)
        return HealthResponse(
            status=ServiceStatus.DEGRADED if degraded else ServiceStatus.OK,
            service=self._settings.app_name,
            version=self._settings.app_version,
            environment=self._settings.ENV.value,
            dependencies=dependencies,
        )
