"""The Home Assistant WebSocket adapter against a fake HA server."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer

from app.adapters.ha_client import HAConnection
from app.adapters.homeassistant import HomeAssistantAdapter
from app.config import Settings
from app.models import Activity, CommandName, CommandRequest

TOKEN = "valid-token-abcdef"


class FakeHA:
    def __init__(self) -> None:
        self.auth_attempts = 0
        self.service_calls: list[dict[str, Any]] = []
        self.sockets: list[web.WebSocketResponse] = []
        self.fail_service = False
        self.registry = [
            {"entity_id": "vacuum.robots", "platform": "ecovacs", "device_id": "d",
             "unique_id": "did1", "disabled_by": None},
            {"entity_id": "sensor.robots_battery", "platform": "ecovacs", "device_id": "d",
             "unique_id": "did1_battery_level", "disabled_by": None},
            {"entity_id": "image.robots_map", "platform": "ecovacs", "device_id": "d",
             "unique_id": "did1_map", "disabled_by": None},
        ]
        self.states = [
            {"entity_id": "vacuum.robots", "state": "docked",
             "attributes": {"supported_features": 4 | 8 | 16 | 256 | 512 | 8192,
                            "rooms": {"Virtuve": 3}},
             "last_updated": "2026-10-25T10:00:00+00:00"},
            {"entity_id": "sensor.robots_battery", "state": "91", "attributes": {},
             "last_updated": "2026-10-25T10:00:00+00:00"},
        ]

    async def ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.sockets.append(ws)
        await ws.send_json({"type": "auth_required"})
        msg = await ws.receive_json()
        self.auth_attempts += 1
        if msg.get("access_token") != TOKEN:
            await ws.send_json({"type": "auth_invalid", "message": "bad"})
            await ws.close()
            return ws
        await ws.send_json({"type": "auth_ok", "ha_version": "2026.10.1"})
        async for raw in ws:
            if raw.type != WSMsgType.TEXT:
                break
            msg = raw.json()
            mid, mtype = msg["id"], msg["type"]
            result: Any = None
            success = True
            if mtype == "config/entity_registry/list":
                result = self.registry
            elif mtype == "config/device_registry/list":
                result = [{"id": "d", "name": "Robis", "model": "DEEBOT X9 PRO OMNI"}]
            elif mtype == "get_states":
                result = self.states
            elif mtype == "call_service":
                self.service_calls.append(msg)
                if self.fail_service:
                    success = False
            out = {"id": mid, "type": "result", "success": success, "result": result}
            if not success:
                out["error"] = {"code": "service_validation_error", "message": "nope"}
            await ws.send_json(out)
        return ws

    async def image(self, request: web.Request) -> web.Response:
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return web.Response(status=401)
        return web.Response(body=b"<svg/>", content_type="image/svg+xml")

    async def push_state(self, entity_id: str, state: str, attrs: dict | None = None) -> None:
        new = {"entity_id": entity_id, "state": state, "attributes": attrs or {},
               "last_updated": "2026-10-25T10:05:00+00:00"}
        for ws in self.sockets:
            if not ws.closed:
                await ws.send_json({"id": 1, "type": "event", "event": {
                    "event_type": "state_changed",
                    "data": {"entity_id": entity_id, "new_state": new, "old_state": None}}})


@pytest.fixture
async def fake_ha():
    fake = FakeHA()
    app = web.Application()
    app.router.add_get("/api/websocket", fake.ws)
    app.router.add_get("/api/image_proxy/{entity_id}", fake.image)
    server = TestServer(app)
    await server.start_server()
    yield fake, f"http://{server.host}:{server.port}"
    await server.close()


async def wait_until(predicate, timeout=3.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not predicate():
        if loop.time() > end:
            raise AssertionError("condition not met")
        await asyncio.sleep(0.02)


def make_settings(url: str, token: str = TOKEN) -> Settings:
    return Settings.from_env({"HA_URL": url, "HA_TOKEN": token, "AUTH_DISABLED": "true"})


async def test_connects_discovers_and_controls(fake_ha):
    fake, url = fake_ha
    adapter = HomeAssistantAdapter(make_settings(url))
    await adapter.start()
    try:
        await wait_until(lambda: adapter.snapshot.robot_available)
        snap = adapter.snapshot
        assert snap.activity == Activity.DOCKED
        assert snap.battery == 91
        assert snap.model == "DEEBOT X9 PRO OMNI"
        assert snap.rooms[0].name == "Virtuve"

        await adapter.send(CommandRequest(CommandName.CLEAN_ROOMS, {"rooms": ["3"], "cleanings": 1}))
        call = fake.service_calls[-1]
        assert call["domain"] == "vacuum" and call["service"] == "send_command"
        assert call["service_data"]["params"] == {"rooms": "3", "cleanings": 1}

        await fake.push_state("vacuum.robots", "cleaning", fake.states[0]["attributes"])
        await wait_until(lambda: adapter.snapshot.activity == Activity.CLEANING)

        assert await adapter.get_map_svg() == b"<svg/>"
    finally:
        await adapter.stop()


async def test_service_error_becomes_adapter_error(fake_ha):
    from app.adapters.base import AdapterError

    fake, url = fake_ha
    fake.fail_service = True
    adapter = HomeAssistantAdapter(make_settings(url))
    await adapter.start()
    try:
        await wait_until(lambda: adapter.snapshot.backend_connected)
        with pytest.raises(AdapterError) as err:
            await adapter.send(CommandRequest(CommandName.START))
        assert err.value.user_message == "Home Assistant atteicās izpildīt komandu."
    finally:
        await adapter.stop()


async def test_invalid_token_does_not_retry_quickly(fake_ha, monkeypatch):
    fake, url = fake_ha
    monkeypatch.setattr(HAConnection, "MIN_DELAY", 0.01)
    adapter = HomeAssistantAdapter(make_settings(url, token="wrong-token"))
    await adapter.start()
    try:
        await wait_until(lambda: adapter._conn.auth_failed)
        await asyncio.sleep(0.3)
        assert fake.auth_attempts == 1  # waits AUTH_FAILURE_DELAY before trying again
        assert not adapter.snapshot.backend_connected
        diag = await adapter.diagnostics()
        assert diag["ha_auth_failed"] is True
        assert "wrong-token" not in str(diag)
    finally:
        await adapter.stop()


async def test_reconnects_after_disconnect(fake_ha, monkeypatch):
    fake, url = fake_ha
    monkeypatch.setattr(HAConnection, "MIN_DELAY", 0.05)
    adapter = HomeAssistantAdapter(make_settings(url))
    await adapter.start()
    try:
        await wait_until(lambda: adapter.snapshot.backend_connected)
        await fake.sockets[0].close()
        await wait_until(lambda: not adapter.snapshot.backend_connected)
        await wait_until(lambda: adapter.snapshot.backend_connected)
        assert fake.auth_attempts == 2
    finally:
        await adapter.stop()
