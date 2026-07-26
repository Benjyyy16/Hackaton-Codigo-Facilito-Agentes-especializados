"""Ciclo de vida del cliente de Supabase.

``supabase-py`` ofrece un cliente asíncrono real (``acreate_client``), así que los
repositorios pueden ser ``async`` de verdad: no hace falta envolver llamadas bloqueantes en
un ejecutor.

El cliente se crea en el ``lifespan`` de la aplicación y se guarda en el estado de la app,
no en una variable de módulo. Un singleton de importación obligaría a los tests a parchear
globales y ataría el ciclo de vida al orden de los imports.

La clave usada es la de service role: el backend opera como servicio de confianza y necesita
saltarse RLS. La contrapartida está cubierta en el esquema, donde RLS queda activo sin
políticas permisivas para la clave anónima.
"""

from __future__ import annotations

from supabase import AsyncClient, acreate_client

from app.core.config import Settings
from app.core.exceptions import SupabaseError
from app.core.logging import get_logger

logger = get_logger("supabase")

# Tabla usada para la comprobación de salud. Se consulta con límite cero: interesa saber si
# PostgREST responde, no traer datos.
_HEALTH_PROBE_TABLE = "workspaces"


async def create_supabase_client(settings: Settings) -> AsyncClient:
    """Construye el cliente asíncrono de Supabase.

    Los fallos se traducen a ``SupabaseError`` para que ninguna capa superior tenga que
    conocer los tipos de excepción de la librería (RF-7.5).
    """
    try:
        client = await acreate_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value(),
        )
    except Exception as error:  # noqa: BLE001 - frontera con librería externa
        # El mensaje no incluye la excepción original en el texto: podría contener la clave.
        logger.error("No se pudo crear el cliente de Supabase", exc_info=error)
        raise SupabaseError("No se pudo inicializar el cliente de Supabase.") from error

    logger.info("Cliente de Supabase inicializado")
    return client


async def close_supabase_client(client: AsyncClient | None) -> None:
    """Cierra el cliente si la versión instalada lo soporta.

    No todas las versiones de ``supabase-py`` exponen un cierre explícito, y el apagado no es
    lugar para fallar: un error aquí se registra y no se propaga.
    """
    if client is None:
        return
    closer = getattr(client, "aclose", None) or getattr(client, "close", None)
    if closer is None:
        return
    try:
        result = closer()
        if hasattr(result, "__await__"):
            await result
    except Exception as error:  # noqa: BLE001 - el apagado nunca debe romper
        logger.warning("Fallo al cerrar el cliente de Supabase: %s", type(error).__name__)


async def ping(client: AsyncClient) -> bool:
    """Comprueba que PostgREST responde.

    Devuelve un booleano en lugar de elevar, porque quien la usa es el health check y su
    contrato es reportar el estado, no fallar (RF-2.3).
    """
    try:
        await client.table(_HEALTH_PROBE_TABLE).select("id").limit(1).execute()
    except Exception as error:  # noqa: BLE001 - cualquier fallo es "no disponible"
        logger.warning("Supabase no responde: %s", type(error).__name__)
        return False
    return True
