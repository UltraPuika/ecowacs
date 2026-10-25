"""Minimal Home Assistant WebSocket client with careful reconnect behaviour."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]
StateCallback = Callable[[], Awaitable[None]]


class HAError(Exception):
    """A Home Assistant request returned an error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class HAAuthError(Exception):
    """The access token was rejected. Retrying fast would not help."""


class HAConnection:
    """One WebSocket connection to Home Assistant, re-established on failure.

    Reconnect delays grow from 2 s to 60 s. After an authentication failure
    the client waits 10 minutes between attempts so that a wrong token cannot
    hammer Home Assistant (HA bans IPs after repeated failed logins).
    """

    MIN_DELAY = 2.0
    MAX_DELAY = 60.0
    AUTH_FAILURE_DELAY = 600.0

    def __init__(
        self,
        ws_url: str,
        token: str,
        on_event: EventCallback,
        on_connect: StateCallback,
        on_disconnect: StateCallback,
    ) -> None:
        self._ws_url = ws_url
        self._token = token
        self._on_event = on_event
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._task: asyncio.Task[None] | None = None
        self._send_lock = asyncio.Lock()
        self.connected = False
        self.auth_failed = False
        self.ha_version: str | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        """Start the background connection loop."""
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="ha-connection")

    async def stop(self) -> None:
        """Stop the loop and close the connection."""
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._close()

    async def _run(self) -> None:
        delay = self.MIN_DELAY
        while True:
            try:
                await self._connect_and_listen()
                delay = self.MIN_DELAY
            except asyncio.CancelledError:
                raise
            except HAAuthError:
                self.auth_failed = True
                self.last_error = "Home Assistant noraidīja piekļuves pilnvaru (HA_TOKEN)."
                _LOGGER.error("Home Assistant rejected the access token")
                delay = self.AUTH_FAILURE_DELAY
            except (aiohttp.ClientError, OSError, TimeoutError, ConnectionError) as err:
                self.last_error = f"Nav savienojuma ar Home Assistant ({type(err).__name__})."
                _LOGGER.warning("Home Assistant connection failed: %s", type(err).__name__)
            except Exception:
                self.last_error = "Neparedzēta kļūda savienojumā ar Home Assistant."
                _LOGGER.exception("Unexpected Home Assistant connection error")
            finally:
                was_connected = self.connected
                self.connected = False
                self._fail_pending()
                await self._close()
                if was_connected:
                    await self._on_disconnect()
            await asyncio.sleep(delay)
            delay = min(delay * 2, self.MAX_DELAY)

    async def _connect_and_listen(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(
            self._ws_url, heartbeat=30, timeout=aiohttp.ClientWSTimeout(ws_close=10)
        )
        msg = await self._ws.receive_json(timeout=15)
        if msg.get("type") != "auth_required":
            raise ConnectionError("Unexpected handshake")
        await self._ws.send_json({"type": "auth", "access_token": self._token})
        msg = await self._ws.receive_json(timeout=15)
        if msg.get("type") == "auth_invalid":
            raise HAAuthError
        if msg.get("type") != "auth_ok":
            raise ConnectionError("Unexpected auth response")

        self.ha_version = msg.get("ha_version")
        self.auth_failed = False
        self.last_error = None
        self.connected = True
        _LOGGER.info("Connected to Home Assistant %s", self.ha_version)

        reader = asyncio.create_task(self._read_loop())
        try:
            await self._on_connect()
            await reader
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader

    async def _read_loop(self) -> None:
        assert self._ws is not None
        async for raw in self._ws:
            if raw.type != aiohttp.WSMsgType.TEXT:
                if raw.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                    break
                continue
            data = raw.json()
            messages = data if isinstance(data, list) else [data]
            for msg in messages:
                await self._handle(msg)
        raise ConnectionError("WebSocket closed")

    async def _handle(self, msg: dict[str, Any]) -> None:
        msg_type = msg.get("type")
        if msg_type == "result":
            future = self._pending.pop(msg.get("id", -1), None)
            if future is None or future.done():
                return
            if msg.get("success"):
                future.set_result(msg.get("result"))
            else:
                error = msg.get("error") or {}
                future.set_exception(
                    HAError(str(error.get("code", "unknown")), str(error.get("message", "")))
                )
        elif msg_type == "event":
            try:
                await self._on_event(msg.get("event") or {})
            except Exception:
                _LOGGER.exception("Event handler failed")

    async def call(self, payload: dict[str, Any], timeout: float = 15.0) -> Any:
        """Send a command and wait for its result."""
        if not self.connected or self._ws is None:
            raise ConnectionError("Not connected to Home Assistant")
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        async with self._send_lock:
            msg_id = self._next_id
            self._next_id += 1
            self._pending[msg_id] = future
            await self._ws.send_json({**payload, "id": msg_id})
        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self._pending.pop(msg_id, None)

    def _fail_pending(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Connection lost"))
        self._pending.clear()

    async def _close(self) -> None:
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def close_session(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def http_session(self) -> aiohttp.ClientSession:
        """Shared HTTP session for REST calls."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
