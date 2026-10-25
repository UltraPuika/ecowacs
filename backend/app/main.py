"""FastAPI application."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .adapters import RobotAdapter, create_adapter
from .adapters.base import AdapterError
from .auth import COOKIE_NAME, Authenticator, LoginRateLimiter, load_secret
from .commands import CommandService
from .config import Settings
from .map_svg import render_map
from .models import CommandName, CommandRequest, RobotSnapshot
from .redact import RedactingFilter, redact
from .services import AnnouncementSettings, Announcer, EventLog, HistoryTracker, freshness
from .storage import Storage

_LOGGER = logging.getLogger(__name__)
PUBLIC_PATHS = {"/api/health", "/api/login", "/api/session"}
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "deebot-lv"
MAP_CACHE_SECONDS = 5.0
SVG_CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'"


class AppState:
    """Everything the routes need."""

    def __init__(self, settings: Settings, adapter: RobotAdapter, storage: Storage) -> None:
        self.settings = settings
        self.adapter = adapter
        self.storage = storage
        self.auth = (
            None
            if settings.auth_disabled
            else Authenticator(
                settings.app_password,
                load_secret(settings.secret_key, settings.data_dir),
                settings.session_days,
            )
        )
        self.limiter = LoginRateLimiter()
        self.commands = CommandService(
            adapter, storage, settings.command_timeout, settings.verify_timeout,
            settings.dedupe_window,
        )
        self.history = HistoryTracker(storage, self.commands, adapter)
        self.announcer = Announcer(storage, adapter, self.commands)
        self.event_log = EventLog(storage)
        self.sockets: set[WebSocket] = set()
        self.map_cache: tuple[float, bytes | None] | None = None
        self.map_lock = asyncio.Lock()
        adapter.add_listener(self.event_log.on_snapshot)
        adapter.add_listener(self.history.on_snapshot)
        adapter.add_listener(self.announcer.on_snapshot)
        adapter.add_listener(self._broadcast)
        adapter.add_event_listener(self.history.on_event)
        adapter.add_event_listener(self.announcer.on_event)

    def status(self) -> dict[str, Any]:
        snap = self.adapter.snapshot
        return {
            "robot": snap.to_dict(),
            "freshness": freshness(snap, datetime.now(UTC), self.settings.stale_after),
            "current_session": self.storage.current_session(),
            "server_time": datetime.now(UTC).isoformat(),
            "mode": self.settings.mode,
        }

    async def _broadcast(self, _old: RobotSnapshot, _new: RobotSnapshot) -> None:
        if not self.sockets:
            return
        message = json.dumps({"type": "status", "data": self.status()})
        for ws in list(self.sockets):
            try:
                await ws.send_text(message)
            except Exception:
                self.sockets.discard(ws)

    async def map_svg(self, force: bool = False) -> bytes | None:
        async with self.map_lock:
            now = time.monotonic()
            if not force and self.map_cache and now - self.map_cache[0] < MAP_CACHE_SECONDS:
                return self.map_cache[1]
            svg = await self.adapter.get_map_svg()
            self.map_cache = (now, svg)
            return svg


def _secrets(settings: Settings) -> tuple[str, ...]:
    return tuple(s for s in (settings.ha_token, settings.app_password, settings.secret_key) if s)


def create_app(
    settings: Settings,
    adapter: RobotAdapter | None = None,
    storage: Storage | None = None,
) -> FastAPI:
    """Build the FastAPI app. Tests inject a fake adapter and in-memory storage."""
    adapter = adapter or create_adapter(settings)
    storage = storage or Storage(settings.data_dir / "deebot.sqlite3")
    state = AppState(settings, adapter, storage)
    redacting = RedactingFilter(_secrets(settings))
    for handler in logging.getLogger().handlers:
        handler.addFilter(redacting)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await adapter.start()
        if settings.mode == "demo":
            _LOGGER.warning("DEMO MODE: no real robot is connected")
        yield
        await adapter.stop()

    app = FastAPI(title="Latvian DEEBOT Control", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.app_state = state

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type", "X-Requested-With"],
        )

    def authenticated(request: Request | WebSocket) -> bool:
        return state.auth is None or state.auth.check(request.cookies.get(COOKIE_NAME))

    @app.middleware("http")
    async def guard(request: Request, call_next: Any) -> Response:
        path = request.url.path
        if path.startswith("/api/"):
            if request.method not in ("GET", "HEAD", "OPTIONS") and (
                request.headers.get(CSRF_HEADER) != CSRF_VALUE
            ):
                return JSONResponse({"detail": "Trūkst drošības galvenes."}, status_code=403)
            if path not in PUBLIC_PATHS and not authenticated(request):
                return JSONResponse({"detail": "Nepieciešams pieslēgties."}, status_code=401)
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    # --- session ----------------------------------------------------------------
    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "version": __version__}

    @app.get("/api/session")
    async def session(request: Request) -> dict[str, Any]:
        return {"authenticated": authenticated(request), "auth_required": state.auth is not None}

    @app.post("/api/login")
    async def login(request: Request, response: Response) -> dict[str, Any]:
        if state.auth is None:
            return {"authenticated": True}
        client = request.client.host if request.client else "unknown"
        if state.limiter.blocked(client):
            raise HTTPException(429, "Pārāk daudz mēģinājumu. Pamēģiniet pēc 5 minūtēm.")
        try:
            body = await request.json()
        except ValueError as err:
            raise HTTPException(400, "Nederīgs pieprasījums.") from err
        password = body.get("password") if isinstance(body, dict) else None
        if not isinstance(password, str) or not state.auth.verify_password(password):
            state.limiter.failed(client)
            await asyncio.sleep(0.5)
            raise HTTPException(401, "Nepareiza parole.")
        state.limiter.reset(client)
        response.set_cookie(
            COOKIE_NAME, state.auth.issue(), max_age=state.auth.max_age, httponly=True,
            samesite="strict", secure=settings.secure_cookies, path="/",
        )
        return {"authenticated": True}

    @app.post("/api/logout")
    async def logout(response: Response) -> dict[str, Any]:
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"authenticated": False}

    # --- status and commands -------------------------------------------------------
    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        return state.status()

    @app.post("/api/commands")
    async def command(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
            name = CommandName(body["name"])
            params = body.get("params") or {}
            if not isinstance(params, dict):
                raise TypeError
        except (ValueError, KeyError, TypeError) as err:
            raise HTTPException(400, "Nederīga komanda.") from err
        result = await state.commands.execute(CommandRequest(name, params))
        if name == CommandName.REFRESH_MAP:
            state.map_cache = None
        return result.to_dict()

    # --- map --------------------------------------------------------------------------
    @app.get("/api/map/meta")
    async def map_meta() -> dict[str, Any]:
        snap = state.adapter.snapshot
        try:
            svg = await state.map_svg()
        except AdapterError as err:
            return {"available": False, "error": err.user_message, "updated": None}
        if svg is None:
            return {"available": False, "error": None, "updated": None}
        render = render_map(svg, hide_carpet=False)
        return {
            "available": True,
            "error": None,
            "updated": snap.map_updated.isoformat() if snap.map_updated else None,
            "active_map": snap.active_map,
            "has_pixel_layer": render.has_pixel_layer,
            "carpet_found": render.carpet_found,
        }

    @app.get("/api/map.svg")
    async def map_image(carpets: str = "show") -> Response:
        if carpets not in ("show", "hide"):
            raise HTTPException(400, "Nederīgs parametrs.")
        try:
            svg = await state.map_svg()
        except AdapterError as err:
            raise HTTPException(502, err.user_message) from err
        if svg is None:
            raise HTTPException(404, "Karte nav pieejama.")
        render = render_map(svg, hide_carpet=carpets == "hide")
        return Response(
            render.svg,
            media_type="image/svg+xml",
            headers={"Content-Security-Policy": SVG_CSP, "Cache-Control": "no-store"},
        )

    # --- history --------------------------------------------------------------------
    @app.get("/api/history")
    async def history() -> dict[str, Any]:
        return {"sessions": state.storage.sessions(200)}

    @app.delete("/api/history")
    async def clear_history(request: Request) -> dict[str, Any]:
        body = await request.json() if await request.body() else {}
        if not isinstance(body, dict) or body.get("confirm") is not True:
            raise HTTPException(400, "Nepieciešams apstiprinājums.")
        state.storage.clear_history()
        state.storage.add_event("info", "history", "Vēsture notīrīta.")
        return {"ok": True}

    @app.get("/api/events")
    async def events() -> dict[str, Any]:
        return {"events": state.storage.events(200), "commands": state.storage.commands(100)}

    # --- announcements ----------------------------------------------------------------
    @app.get("/api/announcements")
    async def get_announcements() -> dict[str, Any]:
        return asdict(state.announcer.settings)

    @app.put("/api/announcements")
    async def put_announcements(request: Request) -> dict[str, Any]:
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "Nederīgi dati.")
        settings_obj = AnnouncementSettings.from_dict(body)
        try:
            state.announcer.save(settings_obj)
        except ValueError as err:
            raise HTTPException(400, str(err)) from err
        return asdict(settings_obj)

    @app.get("/api/announcements/targets")
    async def announcement_targets() -> dict[str, Any]:
        try:
            targets = await state.adapter.speech_targets()
        except AdapterError as err:
            raise HTTPException(503, err.user_message) from err
        except (ConnectionError, TimeoutError) as err:
            raise HTTPException(503, "Nav savienojuma ar Home Assistant.") from err
        return asdict(targets)

    @app.post("/api/announcements/test")
    async def announcement_test(request: Request) -> dict[str, Any]:
        body = await request.json()
        settings_obj = AnnouncementSettings.from_dict(body if isinstance(body, dict) else {})
        settings_obj.enabled = True
        try:
            settings_obj.validate()
        except ValueError as err:
            raise HTTPException(400, str(err)) from err
        problems = await state.announcer.test(settings_obj)
        return {"ok": not problems, "problems": problems}

    # --- diagnostics ------------------------------------------------------------------
    async def diagnostics_data() -> dict[str, Any]:
        try:
            adapter_diag = await state.adapter.diagnostics()
        except Exception as err:  # diagnostics must never fail completely
            adapter_diag = {"error": type(err).__name__}
        data = {
            "app_version": __version__,
            "generated_at": datetime.now(UTC).isoformat(),
            "mode": settings.mode,
            "auth_enabled": state.auth is not None,
            "status": state.status(),
            "adapter": adapter_diag,
            "recent_events": state.storage.events(100),
            "recent_commands": state.storage.commands(50),
        }
        return redact(data, _secrets(settings))

    @app.get("/api/diagnostics")
    async def diagnostics() -> dict[str, Any]:
        return await diagnostics_data()

    @app.get("/api/diagnostics/export")
    async def diagnostics_export() -> Response:
        data = await diagnostics_data()
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        return Response(
            json.dumps(data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="deebot-diagnostika-{stamp}.json"'},
        )

    @app.post("/api/diagnostics/rediscover")
    async def rediscover() -> dict[str, Any]:
        method = getattr(state.adapter, "rediscover", None)
        if method is None:
            return {"ok": True}
        try:
            await method()
        except Exception as err:
            raise HTTPException(503, "Neizdevās nolasīt Home Assistant datus.") from err
        return {"ok": True}

    # --- live updates -------------------------------------------------------------------
    @app.websocket("/api/ws")
    async def websocket(ws: WebSocket) -> None:
        if not authenticated(ws):
            await ws.close(code=4401)
            return
        origin = ws.headers.get("origin")
        host = ws.headers.get("host")
        if origin and not (
            origin.split("://", 1)[-1] == host or origin in settings.cors_origins
        ):
            await ws.close(code=4403)
            return
        await ws.accept()
        state.sockets.add(ws)
        try:
            await ws.send_text(json.dumps({"type": "status", "data": state.status()}))
            while True:
                try:
                    await asyncio.wait_for(ws.receive_text(), timeout=30)
                except TimeoutError:
                    # periodic refresh keeps "last update" and staleness current
                    await ws.send_text(json.dumps({"type": "status", "data": state.status()}))
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            state.sockets.discard(ws)
            with contextlib.suppress(Exception):
                await ws.close()

    return app


def build() -> FastAPI:
    """Entry point for uvicorn (``app.main:build``, factory mode)."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    return create_app(Settings.from_env())
