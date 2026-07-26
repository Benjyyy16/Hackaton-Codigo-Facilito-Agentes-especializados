"""Registro de providers.

Resuelve un provider por nombre. Es el único punto donde la aplicación busca una integración, y
la razón de que añadir una nueva no obligue a tocar rutas ni servicios.

Un provider **sin credenciales no se registra**. La alternativa, registrarlo y dejar que falle
al usarlo, obligaría a cada consumidor a distinguir "no configurado" de "caído", y haría que
``GET /providers`` inventara estados para integraciones que nadie configuró.
"""

from __future__ import annotations

import asyncio

from app.core.exceptions import ProviderNotAvailableError
from app.core.logging import get_logger
from app.providers.base import EventSourceProvider
from app.schemas.common import DependencyStatus
from app.schemas.events import ProviderName
from app.schemas.providers import (
    ProviderCapability,
    ProviderHealth,
    ProviderInfo,
)

logger = get_logger("providers.registry")


class ProviderRegistry:
    """Providers disponibles en esta instancia."""

    def __init__(self) -> None:
        self._sources: dict[ProviderName, EventSourceProvider] = {}

    def register(self, provider: EventSourceProvider) -> None:
        """Añade un provider, comprobando que cumple el puerto.

        La comprobación en tiempo de registro convierte un error de implementación en un fallo
        de arranque, en lugar de en un ``AttributeError`` durante una petición. El protocolo es
        ``runtime_checkable``, así que verifica la presencia de los métodos, no sus firmas; es
        una red parcial, pero cubre el error más habitual, que es olvidar uno.
        """
        if not isinstance(provider, EventSourceProvider):
            raise TypeError(
                f"{type(provider).__name__} no implementa EventSourceProvider."
            )
        if provider.name in self._sources:
            raise ValueError(f"El provider {provider.name.value} ya está registrado.")

        self._sources[provider.name] = provider
        logger.info("Provider registrado: %s", provider.name.value)

    def get(self, name: ProviderName | str) -> EventSourceProvider:
        """Devuelve un provider por nombre.

        Eleva ``ProviderNotAvailableError`` si no está registrado, que se traduce a ``404``: un
        provider no configurado es indistinguible, para quien llama, de uno que no existe.
        """
        try:
            key = ProviderName(name)
        except ValueError as error:
            raise ProviderNotAvailableError(
                f"Provider desconocido: {name}", details={"provider": str(name)}
            ) from error

        provider = self._sources.get(key)
        if provider is None:
            raise ProviderNotAvailableError(
                f"El provider {key.value} no está configurado en esta instancia.",
                details={"provider": key.value},
            )
        return provider

    def names(self) -> list[ProviderName]:
        return sorted(self._sources, key=lambda item: item.value)

    def event_sources(self) -> list[EventSourceProvider]:
        return [self._sources[name] for name in self.names()]

    def with_capability(
        self, capability: ProviderCapability
    ) -> list[EventSourceProvider]:
        """Providers que declaran saber hacer algo concreto."""
        return [
            provider
            for provider in self.event_sources()
            if capability in provider.capabilities
        ]

    def __len__(self) -> int:
        return len(self._sources)

    def __contains__(self, name: object) -> bool:
        return name in self._sources

    # --- Ciclo de vida agregado ---------------------------------------------------

    async def connect_all(self) -> None:
        """Conecta todos los providers registrados.

        El fallo de uno no impide conectar los demás ni arrancar el servicio: quedará reflejado
        en su salud. Que Notion esté caído no es motivo para no ingerir de Jira.
        """
        for provider in self.event_sources():
            try:
                await provider.connect()
            except Exception as error:  # noqa: BLE001 - el arranque debe completarse
                logger.error(
                    "El provider %s no pudo conectar", provider.name.value, exc_info=error
                )

    async def close_all(self) -> None:
        """Cierra todos los providers. Ningún fallo al apagar se propaga."""
        for provider in self.event_sources():
            try:
                await provider.close()
            except Exception as error:  # noqa: BLE001 - el apagado nunca debe romper
                logger.warning(
                    "Fallo al cerrar el provider %s: %s",
                    provider.name.value,
                    type(error).__name__,
                )

    async def health_all(self) -> list[ProviderHealth]:
        """Comprueba todos los providers en paralelo.

        En paralelo porque en serie el tiempo del health check sería la suma de todos los
        providers, y con cinco integraciones lentas eso deja de ser un health check.
        """
        providers = self.event_sources()
        if not providers:
            return []

        results = await asyncio.gather(
            *(provider.health() for provider in providers), return_exceptions=True
        )

        healths: list[ProviderHealth] = []
        for provider, result in zip(providers, results, strict=True):
            if isinstance(result, ProviderHealth):
                healths.append(result)
            else:
                # ``health()`` no debería elevar, pero si lo hace no puede tumbar el resto.
                healths.append(
                    ProviderHealth(
                        provider=provider.name.value,
                        status=DependencyStatus.DOWN,
                        detail=type(result).__name__,
                    )
                )
        return healths

    async def describe(self) -> list[ProviderInfo]:
        """Describe los providers registrados y su salud, para ``GET /providers``."""
        healths = {health.provider: health for health in await self.health_all()}
        return [
            ProviderInfo(
                provider=provider.name,
                kind=provider.kind,
                capabilities=sorted(provider.capabilities, key=lambda item: item.value),
                health=healths.get(provider.name.value),
            )
            for provider in self.event_sources()
        ]
