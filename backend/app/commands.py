"""Safe command execution: validation, duplicate prevention, timeouts, verification."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .adapters.base import AdapterError, RobotAdapter, UnsupportedError
from .models import (
    EXPECTED_ACTIVITIES,
    MOTION_COMMANDS,
    Activity,
    CommandName,
    CommandRequest,
    CommandResult,
    CommandStatus,
    RobotSnapshot,
)
from .storage import Storage

_LOGGER = logging.getLogger(__name__)

CAPABILITY_FOR = {
    CommandName.START: "start",
    CommandName.RESUME: "start",
    CommandName.PAUSE: "pause",
    CommandName.STOP: "stop",
    CommandName.RETURN_TO_BASE: "return_to_base",
    CommandName.LOCATE: "locate",
    CommandName.CLEAN_ROOMS: "clean_rooms",
    CommandName.CLEAN_ZONE: "clean_zone",
    CommandName.SET_FAN_SPEED: "fan_speed",
    CommandName.SET_WORK_MODE: "work_mode",
    CommandName.SET_ACTIVE_MAP: "active_map",
    CommandName.EMPTY_DUSTBIN: "empty_dustbin",
    CommandName.REFRESH_MAP: "map",
}

CONFIRMED_TEXT = {
    CommandName.START: "Robots sāka tīrīšanu.",
    CommandName.CLEAN_ROOMS: "Robots sāka tīrīt izvēlētās telpas.",
    CommandName.CLEAN_ZONE: "Robots sāka tīrīt izvēlēto zonu.",
    CommandName.RESUME: "Robots turpina tīrīšanu.",
    CommandName.PAUSE: "Tīrīšana ir nopauzēta.",
    CommandName.STOP: "Tīrīšana ir apturēta.",
    CommandName.RETURN_TO_BASE: "Robots brauc uz staciju.",
    CommandName.SET_FAN_SPEED: "Sūkšanas jauda nomainīta.",
    CommandName.SET_WORK_MODE: "Tīrīšanas veids nomainīts.",
    CommandName.SET_ACTIVE_MAP: "Karte nomainīta.",
    CommandName.SET_SETTING: "Iestatījums saglabāts.",
}
DONE_TEXT = {
    CommandName.LOCATE: "Robots atskaņo skaņu.",
    CommandName.EMPTY_DUSTBIN: "Stacija iztukšo putekļu tvertni.",
    CommandName.REFRESH_MAP: "Karte tiek atjaunota no robota.",
}
SENT_TEXT = (
    "Komanda nosūtīta, bet robots vēl nav apstiprinājis, ka to izpilda. "
    "Pēc brīža pārbaudiet robota stāvokli."
)
SETTING_SENT_TEXT = "Komanda nosūtīta, bet robots vēl nav apstiprinājis izmaiņas."
START_COMMANDS = frozenset({CommandName.START, CommandName.CLEAN_ROOMS, CommandName.CLEAN_ZONE})


class ValidationError(Exception):
    """Invalid command parameters. Message is Latvian."""


def _choice(value: Any, options: tuple[str, ...]) -> str:
    if not isinstance(value, str) or value not in options:
        raise ValidationError("Nederīga izvēle.")
    return value


def _cleanings(params: dict[str, Any]) -> int:
    value = params.get("cleanings", 1)
    if not isinstance(value, int) or isinstance(value, bool) or value not in (1, 2):
        raise ValidationError("Tīrīšanas reižu skaitam jābūt 1 vai 2.")
    return value


def validate(request: CommandRequest, snap: RobotSnapshot) -> CommandRequest:
    """Validate and normalise parameters against the current robot state."""
    p = request.params
    name = request.name
    if name == CommandName.CLEAN_ROOMS:
        rooms = p.get("rooms")
        if not isinstance(rooms, list) or not rooms or len(rooms) > 50:
            raise ValidationError("Izvēlieties vismaz vienu telpu.")
        known = {r.id for r in snap.rooms}
        clean = [str(r) for r in rooms]
        if any(r not in known for r in clean) or len(set(clean)) != len(clean):
            raise ValidationError("Izvēlētā telpa kartē vairs nav atrodama. Atjaunojiet karti.")
        return CommandRequest(name, {"rooms": clean, "cleanings": _cleanings(p)})
    if name == CommandName.CLEAN_ZONE:
        coords = p.get("coordinates")
        if (
            not isinstance(coords, list)
            or len(coords) != 4
            or not all(isinstance(c, int) and not isinstance(c, bool) for c in coords)
            or not all(-100_000 <= c <= 100_000 for c in coords)
        ):
            raise ValidationError("Zonai jānorāda četras veselu skaitļu koordinātas.")
        x1, y1, x2, y2 = coords
        if x1 >= x2 or y1 >= y2:
            raise ValidationError("Zonas koordinātām jābūt x1 < x2 un y1 < y2.")
        return CommandRequest(name, {"coordinates": coords, "cleanings": _cleanings(p)})
    if name == CommandName.SET_FAN_SPEED:
        return CommandRequest(name, {"value": _choice(p.get("value"), snap.fan_speed_options)})
    if name == CommandName.SET_WORK_MODE:
        return CommandRequest(name, {"value": _choice(p.get("value"), snap.work_mode_options)})
    if name == CommandName.SET_ACTIVE_MAP:
        return CommandRequest(name, {"value": _choice(p.get("value"), snap.map_options)})
    if name == CommandName.SET_SETTING:
        key = p.get("key")
        setting = snap.settings.get(key) if isinstance(key, str) else None
        if setting is None:
            raise ValidationError("Šis iestatījums nav pieejams.")
        value = p.get("value")
        if setting.kind == "switch":
            if not isinstance(value, bool):
                raise ValidationError("Nederīga vērtība.")
        elif setting.kind == "select":
            value = _choice(value, setting.options)
        else:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValidationError("Nederīga vērtība.")
            if (setting.min is not None and value < setting.min) or (
                setting.max is not None and value > setting.max
            ):
                raise ValidationError("Vērtība ir ārpus atļautajām robežām.")
        return CommandRequest(name, {"key": key, "value": value})
    if p:
        raise ValidationError("Šai komandai nav parametru.")
    return request


def _verifier(request: CommandRequest) -> Callable[[RobotSnapshot], bool] | None:
    if expected := EXPECTED_ACTIVITIES.get(request.name):
        return lambda s: s.activity in expected
    value = request.params.get("value")
    if request.name == CommandName.SET_FAN_SPEED:
        return lambda s: s.fan_speed == value
    if request.name == CommandName.SET_WORK_MODE:
        return lambda s: s.work_mode == value
    if request.name == CommandName.SET_ACTIVE_MAP:
        return lambda s: s.active_map == value
    if request.name == CommandName.SET_SETTING:
        key = request.params["key"]
        return lambda s: key in s.settings and s.settings[key].value == value
    return None


@dataclass
class _Waiter:
    predicate: Callable[[RobotSnapshot], bool]
    future: asyncio.Future[bool]


FailureCallback = Callable[[CommandRequest, str], Awaitable[None]]


class CommandService:
    """Executes commands one at a time per robot and verifies their effect."""

    def __init__(
        self,
        adapter: RobotAdapter,
        storage: Storage,
        command_timeout: float = 15.0,
        verify_timeout: float = 25.0,
        dedupe_window: float = 4.0,
        setting_verify_timeout: float = 10.0,
    ) -> None:
        self._adapter = adapter
        self._storage = storage
        self._command_timeout = command_timeout
        self._verify_timeout = verify_timeout
        self._setting_verify_timeout = setting_verify_timeout
        self._dedupe_window = dedupe_window
        self._motion_lock = asyncio.Lock()
        self._inflight: set[str] = set()
        self._recent: dict[str, float] = {}
        self._waiters: list[_Waiter] = []
        self._failure_callbacks: list[FailureCallback] = []
        self.last_start: tuple[float, CommandRequest] | None = None
        adapter.add_listener(self._on_snapshot)

    def on_failure(self, callback: FailureCallback) -> None:
        """Register a callback for failed commands."""
        self._failure_callbacks.append(callback)

    def _on_snapshot(self, _old: RobotSnapshot, new: RobotSnapshot) -> None:
        for waiter in list(self._waiters):
            if not waiter.future.done() and waiter.predicate(new):
                waiter.future.set_result(True)

    async def _wait_for(self, predicate: Callable[[RobotSnapshot], bool], timeout: float) -> bool:
        if predicate(self._adapter.snapshot):
            return True
        waiter = _Waiter(predicate, asyncio.get_running_loop().create_future())
        self._waiters.append(waiter)
        try:
            return await asyncio.wait_for(waiter.future, timeout)
        except TimeoutError:
            return False
        finally:
            self._waiters.remove(waiter)

    def _result(self, request: CommandRequest, status: CommandStatus, message: str) -> CommandResult:
        self._storage.add_command(request.name.value, request.params, status.value, message)
        return CommandResult(status, message, request.name.value)

    async def execute(self, request: CommandRequest) -> CommandResult:
        """Validate, send and verify a command."""
        snap = self._adapter.snapshot
        capability = CAPABILITY_FOR.get(request.name)
        if capability and not snap.capabilities.get(capability, False):
            return self._result(
                request, CommandStatus.REJECTED, "Šī funkcija jūsu robotam nav pieejama."
            )
        if not snap.backend_connected:
            return self._result(
                request, CommandStatus.REJECTED,
                "Nav savienojuma ar robotu. Komanda netika nosūtīta.",
            )
        try:
            request = validate(request, snap)
        except ValidationError as err:
            return self._result(request, CommandStatus.REJECTED, str(err))

        key = request.dedupe_key()
        now = time.monotonic()
        if key in self._inflight:
            return self._result(request, CommandStatus.REJECTED, "Šī komanda jau tiek izpildīta.")
        if now - self._recent.get(key, -1e9) < self._dedupe_window:
            return self._result(
                request, CommandStatus.REJECTED,
                "Šī komanda tikko tika nosūtīta. Uzgaidiet dažas sekundes.",
            )
        is_motion = request.name in MOTION_COMMANDS
        if is_motion and self._motion_lock.locked():
            return self._result(
                request, CommandStatus.REJECTED,
                "Iepriekšējā komanda vēl tiek izpildīta. Uzgaidiet.",
            )

        self._inflight.add(key)
        try:
            if is_motion:
                async with self._motion_lock:
                    return await self._run(request)
            return await self._run(request)
        finally:
            self._inflight.discard(key)
            self._recent[key] = time.monotonic()

    async def _run(self, request: CommandRequest) -> CommandResult:
        try:
            await asyncio.wait_for(self._adapter.send(request), self._command_timeout)
        except TimeoutError:
            return await self._fail(
                request, "Robots neatbildēja laikā. Pārbaudiet savienojumu ar robotu."
            )
        except UnsupportedError as err:
            return self._result(request, CommandStatus.REJECTED, err.user_message)
        except AdapterError as err:
            _LOGGER.warning("Command %s failed: %s", request.name, err.detail)
            return await self._fail(request, err.user_message)

        if request.name in START_COMMANDS:
            self.last_start = (time.monotonic(), request)

        predicate = _verifier(request)
        if predicate is None:
            return self._result(request, CommandStatus.DONE, DONE_TEXT.get(request.name, "Izpildīts."))
        motion = request.name in MOTION_COMMANDS
        timeout = self._verify_timeout if motion else self._setting_verify_timeout
        if await self._wait_for(predicate, timeout):
            message = CONFIRMED_TEXT.get(request.name, "Izpildīts.")
            if request.name == CommandName.RETURN_TO_BASE and (
                self._adapter.snapshot.activity == Activity.DOCKED
            ):
                message = "Robots ir stacijā."
            return self._result(request, CommandStatus.CONFIRMED, message)
        return self._result(request, CommandStatus.SENT, SENT_TEXT if motion else SETTING_SENT_TEXT)

    async def _fail(self, request: CommandRequest, message: str) -> CommandResult:
        result = self._result(request, CommandStatus.FAILED, message)
        for callback in self._failure_callbacks:
            try:
                await callback(request, message)
            except Exception:
                _LOGGER.exception("Failure callback failed")
        return result
