"""HTTP API: authentication, CSRF, status, staleness, commands, history, diagnostics."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import CSRF_HEADER, CSRF_VALUE, create_app
from app.map_svg import make_indexed_png
from app.storage import Storage

H = {CSRF_HEADER: CSRF_VALUE}


@pytest.fixture
def client(settings, fake_adapter):
    app = create_app(settings, fake_adapter, Storage(":memory:"))
    with TestClient(app) as c:
        yield c


def login(client):
    r = client.post("/api/login", json={"password": "parole123"}, headers=H)
    assert r.status_code == 200


def test_health_is_public(client):
    assert client.get("/api/health").json()["ok"] is True


def test_status_requires_login(client):
    assert client.get("/api/status").status_code == 401
    assert client.get("/api/session").json() == {"authenticated": False, "auth_required": True}


def test_wrong_password_and_rate_limit(client):
    for _ in range(5):
        r = client.post("/api/login", json={"password": "nepareizi"}, headers=H)
        assert r.status_code == 401
        assert r.json()["detail"] == "Nepareiza parole."
    r = client.post("/api/login", json={"password": "parole123"}, headers=H)
    assert r.status_code == 429


def test_post_without_csrf_header_rejected(client):
    login(client)
    r = client.post("/api/commands", json={"name": "start"})
    assert r.status_code == 403


def test_session_cookie_flags(client):
    r = client.post("/api/login", json={"password": "parole123"}, headers=H)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_tampered_cookie_rejected(client):
    login(client)
    token = client.cookies.get("deebot_session")
    client.cookies.set("deebot_session", token[:-2] + "xx")
    assert client.get("/api/status").status_code == 401


def test_status_content(client):
    login(client)
    data = client.get("/api/status").json()
    assert data["robot"]["battery"] == 80
    assert data["robot"]["activity"] == "docked"
    assert data["freshness"]["stale"] is False
    assert "ha_token" not in str(data) and "super-secret" not in str(data)


async def _set(adapter, changes):
    await adapter.set(**changes)


def test_stale_data_is_flagged(client, fake_adapter):
    login(client)
    client.portal.call(_set, fake_adapter, {"last_update": datetime.now(UTC) - timedelta(hours=2)})
    assert client.get("/api/status").json()["freshness"]["stale"] is True
    client.portal.call(_set, fake_adapter, {"backend_connected": False, "last_update": datetime.now(UTC)})
    fresh = client.get("/api/status").json()["freshness"]
    assert fresh["stale"] is True and "novecojuši" in fresh["reason"]


def test_command_endpoint(client, fake_adapter):
    login(client)
    r = client.post("/api/commands", json={"name": "start"}, headers=H)
    assert r.json()["status"] == "confirmed"
    r = client.post("/api/commands", json={"name": "fly"}, headers=H)
    assert r.status_code == 400
    r = client.post("/api/commands", json={"name": "clean_rooms", "params": {"rooms": ["x"]}}, headers=H)
    assert r.json()["status"] == "rejected"


def test_history_clear_requires_confirmation(client):
    login(client)
    assert client.request("DELETE", "/api/history", headers=H).status_code == 400
    r = client.request("DELETE", "/api/history", json={"confirm": True}, headers=H)
    assert r.status_code == 200


def test_diagnostics_are_redacted(client):
    login(client)
    client.post("/api/commands", json={"name": "locate"}, headers=H)
    text = client.get("/api/diagnostics/export").text
    assert "super-secret-ha-token-123" not in text
    assert "parole123" not in text
    assert "abc.def-secret-token" not in text
    assert "REDACTED" in text


def test_map_carpet_toggle(client, fake_adapter):
    login(client)
    palette = bytes([0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3])
    png = make_indexed_png(2, 1, [[1, 3]], palette)
    fake_adapter.svg = (
        b'<svg><image href="data:image/png;base64,' + base64.b64encode(png) + b'"/></svg>'
    )
    meta = client.get("/api/map/meta").json()
    assert meta["available"] and meta["carpet_found"] is True
    assert meta["view_box"] is None and meta["zone_rotation"] is None
    shown = client.get("/api/map.svg?carpets=show")
    hidden = client.get("/api/map.svg?carpets=hide")
    assert shown.headers["content-type"].startswith("image/svg+xml")
    assert "default-src 'none'" in shown.headers["content-security-policy"]
    assert shown.content != hidden.content
    assert client.get("/api/map.svg?carpets=<script>").status_code == 400


def test_map_view_box_without_known_rotation(client, fake_adapter):
    login(client)
    fake_adapter.svg = b'<svg viewBox="-100 -50 200 100" xmlns="http://www.w3.org/2000/svg"></svg>'
    meta = client.get("/api/map/meta").json()
    assert meta["view_box"] == [-100, -50, 200, 100]
    assert meta["zone_rotation"] is None  # adapter cannot map SVG units to robot coordinates


def test_no_map(client, fake_adapter):
    login(client)
    fake_adapter.svg = None
    assert client.get("/api/map/meta").json()["available"] is False
    assert client.get("/api/map.svg").status_code == 404


def test_announcement_settings_validation(client):
    login(client)
    r = client.put("/api/announcements", json={"enabled": True}, headers=H)
    assert r.status_code == 400
    ok = {"enabled": True, "tts_entity": "tts.piper", "media_player": "media_player.virtuve",
          "volume": 0.5}
    assert client.put("/api/announcements", json=ok, headers=H).status_code == 200
    assert client.get("/api/announcements").json()["tts_entity"] == "tts.piper"
    bad = dict(ok, tts_entity="script.evil")
    assert client.put("/api/announcements", json=bad, headers=H).status_code == 400


def test_announcement_test_endpoint(client, fake_adapter):
    login(client)
    body = {"tts_entity": "tts.piper", "media_player": "media_player.virtuve"}
    r = client.post("/api/announcements/test", json=body, headers=H)
    assert r.json()["ok"] is True
    assert fake_adapter.spoken[0][2].startswith("Šis ir pārbaudes paziņojums")


def test_websocket_requires_auth_and_sends_status(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws") as ws:
            ws.receive_text()
    login(client)
    with client.websocket_connect("/api/ws") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "status"
        assert msg["data"]["robot"]["battery"] == 80


def test_auth_disabled_mode(tmp_path, fake_adapter):
    from app.config import Settings

    s = Settings.from_env({"MODE": "demo", "AUTH_DISABLED": "true", "DATA_DIR": str(tmp_path)})
    with TestClient(create_app(s, fake_adapter, Storage(":memory:"))) as c:
        assert c.get("/api/status").status_code == 200
