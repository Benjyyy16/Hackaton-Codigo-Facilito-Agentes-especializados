"""Punto de entrada de la aplicación.

Usa ``lifespan`` en lugar de ``@app.on_event``, que está obsoleto. Los recursos de vida larga
(cliente de Supabase y, más adelante, cliente de Jira) se crean una vez al arrancar y se
guardan en ``app.state``, no en variables de módulo.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI, Request, Response

from app.api.routes import health
from app.core.config import APP_NAME, APP_VERSION, Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger, set_request_id
from app.integrations.jira.client import (
    close_jira_http_client,
    create_jira_http_client,
)
from app.integrations.supabase.client import (
    close_supabase_client,
    create_supabase_client,
)

logger = get_logger("app")

REQUEST_ID_HEADER: Final[str] = "X-Request-ID"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Crea y libera los recursos de vida larga.

    Un fallo al crear el cliente de Supabase no impide arrancar: el servicio queda en estado
    degradado y ``GET /health`` lo reporta. Abortar el arranque dejaría al operador sin forma
    de consultar qué falla (RF-2.3).
    """
    settings: Settings = app.state.settings
    app.state.supabase = None
    app.state.jira_http = None

    try:
        app.state.supabase = await create_supabase_client(settings)
    except Exception as error:  # noqa: BLE001 - el arranque debe completarse
        logger.error(
            "Arranque sin cliente de Supabase; el servicio queda degradado",
            exc_info=error,
        )

    # El cliente HTTP de Jira es de vida larga y se reutiliza: crear uno por petición
    # desperdiciaría el pool de conexiones y el handshake TLS.
    app.state.jira_http = create_jira_http_client(settings)

    logger.info(
        "Servicio %s %s iniciado en entorno %s",
        settings.app_name,
        settings.app_version,
        settings.ENV.value,
    )
    try:
        yield
    finally:
        await close_jira_http_client(app.state.jira_http)
        await close_supabase_client(app.state.supabase)
        app.state.jira_http = None
        app.state.supabase = None
        logger.info("Servicio detenido")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación.

    Recibe ``settings`` como parámetro para que los tests puedan inyectar una configuración
    sin depender del entorno del proceso.
    """
    resolved = settings or get_settings()
    configure_logging(resolved)

    app = FastAPI(
        title="Commitment Twin API",
        version=APP_VERSION,
        summary="Detección de compromisos en riesgo a partir de señales de Jira",
        description=(
            "Backend que ingiere eventos de Jira, los analiza con agentes especializados "
            "y difunde el resultado en tiempo real."
        ),
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.supabase = None
    app.state.jira_http = None

    @app.middleware("http")
    async def _correlate_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Asigna un identificador de correlación y lo devuelve al cliente.

        Si el cliente ya envió uno, se respeta: así una traza que atraviesa varios servicios
        mantiene el mismo identificador (RNF-2.2).
        """
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            # Se limpia al terminar para que el contexto no se filtre a otra petición
            # atendida por la misma tarea.
            set_request_id(None)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    register_exception_handlers(app)
    app.include_router(health.router)

    return app


if __name__ == "__main__":  # pragma: no cover - arranque manual
    import uvicorn

    # Se arranca con la factoría, no con una instancia de módulo. Instanciar la app al
    # importar obligaría a tener el entorno completo resuelto solo para importar el módulo,
    # incluida la recolección de tests.
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
        reload=not get_settings().is_production,
    )
