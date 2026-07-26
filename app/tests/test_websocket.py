"""Tests del gestor de conexiones WebSocket y la ruta /ws/events.

Valida:
- Ciclo de vida de conexiones (connect/disconnect).
- Tolerancia a fallos de sockets individuales durante la difusión.
- Formato del sobre WsEvent y serialización JSON.
- Ruta de eventos con ping/pong y descarte de mensajes desconocidos.
- Seguridad de concurrencia en mutaciones del conjunto.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.websocket.manager import ConnectionManager, EventType, WsEvent, EVENT_VERSION
from app.websocket.routes import router


# --- Helpers -------------------------------------------------------------------


class FakeWebSocket:
    """Doble de WebSocket con send_json configurable."""

    def __init__(self, *, should_fail: bool = False) -> None:
        self._fail = should_fail
        self.accepted = False
        self.sent: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: Any) -> None:
        if self._fail:
            raise RuntimeError("socket roto")
        self.sent.append(data)


def _make_event(**overrides: Any) -> WsEvent:
    defaults = {
        "type": EventType.RISK_CASE_CREATED,
        "commitment_id": uuid4(),
        "data": {"score": 75},
    }
    defaults.update(overrides)
    return WsEvent(**defaults)


def _build_ws_app() -> FastAPI:
    """Mini app con la ruta WS y un manager inyectado."""
    app = FastAPI()
    app.include_router(router)
    app.state.ws_manager = ConnectionManager()
    return app


# --- Tests: ConnectionManager --------------------------------------------------


@pytest.mark.asyncio
async def test_connect_adds_to_set():
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    await mgr.connect(ws)  # type: ignore[arg-type]
    assert mgr.active_connections == 1


@pytest.mark.asyncio
async def test_disconnect_removes_from_set():
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    await mgr.connect(ws)  # type: ignore[arg-type]
    await mgr.disconnect(ws)  # type: ignore[arg-type]
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_disconnect_twice_is_noop():
    """discard, no remove: la segunda llamada no eleva."""
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    await mgr.connect(ws)  # type: ignore[arg-type]
    await mgr.disconnect(ws)  # type: ignore[arg-type]
    await mgr.disconnect(ws)  # type: ignore[arg-type]
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_broadcast_no_clients_returns_zero():
    mgr = ConnectionManager()
    delivered = await mgr.broadcast(_make_event())
    assert delivered == 0


@pytest.mark.asyncio
async def test_broadcast_to_three_clients():
    mgr = ConnectionManager()
    sockets = [FakeWebSocket() for _ in range(3)]
    for ws in sockets:
        await mgr.connect(ws)  # type: ignore[arg-type]
    delivered = await mgr.broadcast(_make_event())
    assert delivered == 3
    # Cada socket recibió exactamente un mensaje
    for ws in sockets:
        assert len(ws.sent) == 1


@pytest.mark.asyncio
async def test_broken_socket_removed_others_receive():
    """Un socket que falla se retira; los demás sí reciben."""
    mgr = ConnectionManager()
    good1 = FakeWebSocket()
    broken = FakeWebSocket(should_fail=True)
    good2 = FakeWebSocket()

    await mgr.connect(good1)  # type: ignore[arg-type]
    await mgr.connect(broken)  # type: ignore[arg-type]
    await mgr.connect(good2)  # type: ignore[arg-type]

    delivered = await mgr.broadcast(_make_event())
    assert delivered == 2
    # El roto se retiró
    assert mgr.active_connections == 2
    assert len(good1.sent) == 1
    assert len(good2.sent) == 1


# --- Tests: WsEvent -----------------------------------------------------------


def test_ws_event_has_required_fields():
    """El sobre lleva type, version, occurred_at."""
    event = _make_event()
    assert event.type == EventType.RISK_CASE_CREATED
    assert event.version == EVENT_VERSION
    assert isinstance(event.occurred_at, datetime)


def test_ws_event_carries_ids():
    cid = uuid4()
    rcid = uuid4()
    pid = uuid4()
    event = WsEvent(
        type=EventType.ALERT_CREATED,
        commitment_id=cid,
        risk_case_id=rcid,
        project_id=pid,
        data={},
    )
    assert event.commitment_id == cid
    assert event.risk_case_id == rcid
    assert event.project_id == pid


def test_model_dump_json_serializes_uuid_and_datetime():
    """model_dump(mode='json') convierte UUID a str y datetime a ISO."""
    cid = uuid4()
    event = WsEvent(
        type=EventType.DECISION_APPROVED,
        commitment_id=cid,
        data={"x": 1},
    )
    payload = event.model_dump(mode="json")
    assert isinstance(payload["commitment_id"], str)
    assert payload["commitment_id"] == str(cid)
    assert isinstance(payload["occurred_at"], str)
    assert isinstance(payload["version"], str)
    assert payload["version"] == EVENT_VERSION


# --- Tests: ruta /ws/events ----------------------------------------------------


def test_ws_route_ping_pong():
    """El servidor responde 'pong' a 'ping'."""
    app = _build_ws_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/events") as ws:
        ws.send_text("ping")
        data = ws.receive_json()
        assert data == {"type": "pong"}


def test_ws_route_ignores_other_messages():
    """Mensajes que no sean 'ping' no generan respuesta."""
    app = _build_ws_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/events") as ws:
        ws.send_text("hola")
        ws.send_text("ping")
        # Solo debe llegar la respuesta del ping, no del 'hola'
        data = ws.receive_json()
        assert data == {"type": "pong"}


def test_ws_route_disconnect_removes_from_manager():
    """Cuando el cliente cierra, se retira del manager."""
    app = _build_ws_app()
    manager: ConnectionManager = app.state.ws_manager
    client = TestClient(app)
    with client.websocket_connect("/ws/events"):
        # Dentro del bloque, está conectado
        assert manager.active_connections == 1
    # Fuera, se desconectó
    assert manager.active_connections == 0


# --- Tests: concurrencia -------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_connects_safe():
    """10 connect simultáneos no corrompen el conjunto interno."""
    mgr = ConnectionManager()
    sockets = [FakeWebSocket() for _ in range(10)]

    async def do_connect(ws: FakeWebSocket) -> None:
        await mgr.connect(ws)  # type: ignore[arg-type]

    await asyncio.gather(*(do_connect(ws) for ws in sockets))
    assert mgr.active_connections == 10


@pytest.mark.asyncio
async def test_concurrent_disconnects_safe():
    """10 disconnect simultáneos no elevan ni corrompen."""
    mgr = ConnectionManager()
    sockets = [FakeWebSocket() for _ in range(10)]
    for ws in sockets:
        await mgr.connect(ws)  # type: ignore[arg-type]

    async def do_disconnect(ws: FakeWebSocket) -> None:
        await mgr.disconnect(ws)  # type: ignore[arg-type]

    await asyncio.gather(*(do_disconnect(ws) for ws in sockets))
    assert mgr.active_connections == 0


@pytest.mark.asyncio
async def test_len_matches_active_connections():
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    await mgr.connect(ws)  # type: ignore[arg-type]
    assert len(mgr) == 1
    await mgr.disconnect(ws)  # type: ignore[arg-type]
    assert len(mgr) == 0
