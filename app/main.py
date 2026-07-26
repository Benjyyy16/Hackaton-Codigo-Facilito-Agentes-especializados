"""Punto de entrada de la aplicación.

Usa ``lifespan`` en lugar de ``@app.on_event``, que está obsoleto. Los recursos de vida larga se
crean una vez al arrancar y se guardan en ``app.state``, no en variables de módulo.

Este archivo, y solo este, decide qué implementaciones concretas de provider se usan. Es el
extremo de la inyección de dependencias: a partir de aquí todo el mundo habla con puertos.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Final

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    agent_runs as agent_runs_routes,
    agents as agents_routes,
    alerts as alerts_routes,
    auth,
    chat as chat_routes,
    commitments as commitments_routes,
    decisions as decisions_routes,
    demo as demo_routes,
    documents as documents_routes,
    finance,
    health,
    integrations,
    oauth,
    oauth_login,
    orchestrate as orchestrate_routes,
    projects as projects_routes,
    providers as provider_routes,
    risk_cases as risk_cases_routes,
    schema_admin as schema_admin_routes,
)
from app.core.config import APP_VERSION, Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger, set_request_id
from app.core.security import cors_origins_for
from app.providers.github import GitHubProvider
from app.providers.jira import JiraProvider
from app.providers.notion import NotionProvider
from app.providers.registry import ProviderRegistry
from app.providers.slack import SlackProvider
from app.providers.supabase import SupabaseStorageProvider
from app.providers.vercel import VercelProvider
from app.websocket.manager import ConnectionManager
from app.websocket.routes import router as ws_router

logger = get_logger("app")

REQUEST_ID_HEADER: Final[str] = "X-Request-ID"


def build_provider_registry(settings: Settings) -> ProviderRegistry:
    """Construye el registro a partir de la configuración.

    **Solo se registra el provider cuyas credenciales están presentes.** Un provider sin
    configurar no se registra, en lugar de registrarse y fallar al usarlo: así cada consumidor no
    tiene que distinguir "no configurado" de "caído", y ``GET /providers`` no inventa estados para
    integraciones que nadie configuró.

    Añadir GitHub, Notion, AWS o Rightway significa añadir una rama aquí y nada más. Ningún
    servicio, ninguna ruta y ningún agente cambia.
    """
    registry = ProviderRegistry()

    if settings.JIRA_BASE_URL and settings.JIRA_EMAIL:
        registry.register(JiraProvider(settings))

    if settings.GITHUB_TOKEN:
        registry.register(GitHubProvider(settings))

    if settings.NOTION_TOKEN:
        registry.register(NotionProvider(settings))

    if settings.SLACK_BOT_TOKEN:
        registry.register(SlackProvider(settings))

    if settings.VERCEL_TOKEN:
        registry.register(VercelProvider(settings))

    return registry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Crea y libera los recursos de vida larga.

    Un fallo al conectar no impide arrancar: el servicio queda degradado y ``GET /health`` lo
    reporta. Abortar el arranque dejaría al operador sin forma de consultar qué falla (RF-2.3).
    """
    settings: Settings = app.state.settings

    storage = SupabaseStorageProvider(settings)
    try:
        await storage.connect()
    except Exception as error:  # noqa: BLE001 - el arranque debe completarse
        logger.error(
            "Arranque sin almacenamiento; el servicio queda degradado", exc_info=error
        )
    app.state.storage = storage

    registry = build_provider_registry(settings)
    await registry.connect_all()
    app.state.providers = registry

    logger.info(
        "Servicio %s %s iniciado en entorno %s con providers: %s",
        settings.app_name,
        settings.app_version,
        settings.ENV.value,
        ", ".join(name.value for name in registry.names()) or "ninguno",
    )
    try:
        yield
    finally:
        await registry.close_all()
        await storage.close()
        app.state.providers = ProviderRegistry()
        app.state.storage = None
        logger.info("Servicio detenido")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construye la aplicación.

    Recibe ``settings`` como parámetro para que los tests puedan inyectar una configuración sin
    depender del entorno del proceso.
    """
    resolved = settings or get_settings()
    configure_logging(resolved)

    app = FastAPI(
        title="Commitment Twin API",
        version=APP_VERSION,
        summary="Detección de compromisos en riesgo a partir de señales de varios sistemas",
        description=(
            "Backend que ingiere eventos de proveedores externos, los analiza con agentes "
            "especializados y difunde el resultado en tiempo real.\n\n"
            "Las rutas son genéricas: el provider viaja en la URL y se resuelve en el registro."
        ),
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.storage = None
    app.state.providers = ProviderRegistry()
    app.state.ws_manager = ConnectionManager()

    # CORS restringido por entorno.
    #
    # ``allow_origins=["*"]`` junto con ``allow_credentials=True`` es una combinación que
    # los navegadores rechazan y que, si funcionara, permitiría a cualquier sitio hacer
    # peticiones autenticadas contra esta API. Los orígenes se derivan de FRONTEND_URL y
    # del entorno: en producción solo el frontend declarado; en desarrollo también
    # localhost.
    allowed_origins = cors_origins_for(resolved)
    if not allowed_origins:
        # Sin FRONTEND_URL no hay nada que permitir. Se deja la lista vacía en lugar de
        # abrir a todos: un despliegue mal configurado debe fallar de forma visible en el
        # navegador, no quedar abierto en silencio.
        logger.warning(
            "CORS sin orígenes permitidos: falta FRONTEND_URL. "
            "El frontend recibirá errores de CORS hasta que se configure."
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

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
            # Se limpia al terminar para que el contexto no se filtre a otra petición atendida
            # por la misma tarea.
            set_request_id(None)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(finance.router)
    app.include_router(integrations.router)
    app.include_router(oauth.router)
    app.include_router(oauth_login.router)
    app.include_router(agents_routes.router)
    app.include_router(orchestrate_routes.router)
    app.include_router(schema_admin_routes.router)
    app.include_router(chat_routes.router)
    app.include_router(health.router)
    app.include_router(provider_routes.router)
    # Dominio Datgent
    app.include_router(projects_routes.router)
    app.include_router(commitments_routes.router)
    app.include_router(risk_cases_routes.router)
    app.include_router(alerts_routes.router)
    app.include_router(decisions_routes.router)
    app.include_router(agent_runs_routes.router)
    app.include_router(agent_runs_routes.agent_runs_router)
    # RAG y Demo
    app.include_router(documents_routes.router)
    app.include_router(demo_routes.router)
    # WebSocket
    app.include_router(ws_router)

    return app


if __name__ == "__main__":  # pragma: no cover - arranque manual
    import os

    import uvicorn

    # Se arranca con la factoría, no con una instancia de módulo. Instanciar la app al importar
    # obligaría a tener el entorno completo resuelto solo para importar el módulo, incluida la
    # recolección de tests.
    #
    # El puerto viene del entorno porque es lo que hace Render: fija PORT y espera que el
    # proceso escuche ahí. Hardcodearlo funcionaría en local y fallaría en el despliegue.
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        reload=not get_settings().is_production,
    )
