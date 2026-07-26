"""Ruta WebSocket de eventos.

Un único canal, ``/ws/events``, por el que salen todos los tipos de evento. El cliente
discrimina por el campo ``type`` del sobre.

Se elige un canal único en lugar de uno por tipo porque el frontend necesita el orden
relativo entre eventos de distinta clase: que la alerta llegue después del caso de
riesgo que la originó no es casual, y con canales separados ese orden no está
garantizado.

SEGURIDAD: el canal es de solo lectura desde el punto de vista del cliente. Los mensajes
que envía se descartan, salvo ``ping``. Aceptar comandos por WebSocket duplicaría la
superficie de la API sin la validación de las rutas HTTP.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.websocket.manager import ConnectionManager

logger = get_logger("websocket.routes")

router = APIRouter(tags=["websocket"])


def get_manager(websocket: WebSocket) -> ConnectionManager:
    """Recupera el gestor del estado de la aplicación.

    Vive en ``app.state`` y no en una variable de módulo para que los tests puedan
    inyectar uno propio y para que su ciclo de vida no dependa del orden de los imports.
    """
    manager = getattr(websocket.app.state, "ws_manager", None)
    if manager is None:  # pragma: no cover - la app siempre lo crea en create_app
        manager = ConnectionManager()
        websocket.app.state.ws_manager = manager
    return manager


@router.websocket("/ws/events")
async def events_channel(websocket: WebSocket) -> None:
    """Canal de eventos en tiempo real.

    El bucle de recepción existe aunque no se procesen comandos: sin leer del socket, el
    servidor no detecta la desconexión del cliente y la conexión quedaría en el conjunto
    hasta el siguiente intento de envío.
    """
    manager = get_manager(websocket)
    await manager.connect(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            # Se responde solo al latido. Cualquier otro mensaje se ignora: los comandos
            # van por HTTP, donde hay validación y autorización.
            if message.strip().lower() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as error:  # noqa: BLE001 - un cliente no debe tumbar el servidor
        logger.warning("Conexión WebSocket terminada: %s", type(error).__name__)
        await manager.disconnect(websocket)
