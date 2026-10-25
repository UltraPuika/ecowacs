"""Demo adapter: a simulated robot, clearly marked as not real.

Every snapshot it produces has ``demo=True``, and the UI shows a permanent
"DEMO" banner. It exists so the interface can be tried without a robot.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from ..map_svg import make_indexed_png
from ..models import Activity, CommandName, CommandRequest, RobotSnapshot, Room, Setting
from .base import RobotAdapter, SpeechTargets, UnsupportedError

_PALETTE = bytes(
    [0, 0, 0, 0xBA, 0xDA, 0xFF, 0x4E, 0x96, 0xE2, 0x1A, 0x81, 0xED]
)  # transparent, floor, wall, carpet (same as deebot-client)


def _demo_map_png() -> bytes:
    w, h = 60, 40
    pixels = []
    for y in range(h):
        row = []
        for x in range(w):
            if x in (0, w - 1) or y in (0, h - 1) or (x == 30 and not 15 < y < 22):
                row.append(2)
            elif 8 <= x <= 20 and 10 <= y <= 25:
                row.append(3)  # a carpet in the "living room"
            else:
                row.append(1)
        pixels.append(row)
    return make_indexed_png(w, h, pixels, _PALETTE)


DEMO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 40">'
    '<image x="0" y="0" width="60" height="40" style="image-rendering: pixelated" '
    'href="data:image/png;base64,' + base64.b64encode(_demo_map_png()).decode() + '"/>'
    '<text x="30" y="22" font-size="4" text-anchor="middle" fill="#900">DEMO</text>'
    "</svg>"
).encode()


class DemoAdapter(RobotAdapter):
    """Simulated robot."""

    is_demo = True

    def __init__(self, step_delay: float = 2.0) -> None:
        super().__init__()
        self._delay = step_delay
        self._tasks: set[asyncio.Task[None]] = set()
        self.spoken: list[str] = []

    async def start(self) -> None:
        now = datetime.now(UTC)
        await self._publish(
            RobotSnapshot(
                backend_connected=True,
                robot_available=True,
                activity=Activity.DOCKED,
                battery=87,
                fan_speed="normal",
                fan_speed_options=("quiet", "normal", "max", "max_plus"),
                work_mode="vacuum_and_mop",
                work_mode_options=("vacuum", "vacuum_and_mop", "mop_after_vacuum"),
                rooms=(
                    Room("1", "Viesistaba"),
                    Room("2", "Virtuve"),
                    Room("3", "Guļamistaba"),
                    Room("4", "Gaitenis"),
                ),
                active_map="Pirmais stāvs",
                map_options=("Pirmais stāvs",),
                map_updated=now,
                station_state="idle",
                last_clean_area=42.0,
                last_clean_minutes=55.0,
                settings={
                    "carpet_auto_fan_boost": Setting("carpet_auto_fan_boost", "switch", True),
                    "continuous_cleaning": Setting("continuous_cleaning", "switch", True),
                    "child_lock": Setting("child_lock", "switch", False),
                    "volume": Setting("volume", "number", 6, 0, 10, 1),
                    "water_amount": Setting("water_amount", "number", 25, 0, 50, 1),
                    "clean_count": Setting("clean_count", "number", 1, 1, 2, 1),
                },
                capabilities={
                    k: True
                    for k in (
                        "start", "pause", "stop", "return_to_base", "locate", "fan_speed",
                        "clean_rooms", "clean_zone", "work_mode", "active_map", "map",
                        "error_codes", "job_finished_event", "empty_dustbin", "announcements",
                    )
                },
                last_update=now,
                robot_name="Demo robots",
                model="DEMO (nav īsts robots)",
                demo=True,
            )
        )

    async def stop(self) -> None:
        for task in list(self._tasks):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _set(self, **changes: Any) -> None:
        await self._publish(replace(self.snapshot, last_update=datetime.now(UTC), **changes))

    def _later(self, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _finish_later(self) -> None:
        await asyncio.sleep(self._delay * 10)
        if self.snapshot.activity == Activity.CLEANING:
            await self._set(activity=Activity.RETURNING)
            await asyncio.sleep(self._delay)
            await self._set(activity=Activity.DOCKED, last_clean_area=18.5, last_clean_minutes=21)
            await self._emit("job_finished", {"result": "finished"})

    async def send(self, request: CommandRequest) -> None:
        await asyncio.sleep(0.2)
        name = request.name
        if name in (CommandName.START, CommandName.RESUME, CommandName.CLEAN_ROOMS, CommandName.CLEAN_ZONE):
            await self._set(activity=Activity.CLEANING)
            self._later(self._finish_later())
        elif name == CommandName.PAUSE:
            await self._set(activity=Activity.PAUSED)
        elif name == CommandName.STOP:
            await self._set(activity=Activity.IDLE)
        elif name == CommandName.RETURN_TO_BASE:
            await self._set(activity=Activity.RETURNING)

            async def dock() -> None:
                await asyncio.sleep(self._delay)
                await self._set(activity=Activity.DOCKED)

            self._later(dock())
        elif name == CommandName.SET_FAN_SPEED:
            await self._set(fan_speed=request.params["value"])
        elif name == CommandName.SET_WORK_MODE:
            await self._set(work_mode=request.params["value"])
        elif name == CommandName.SET_ACTIVE_MAP:
            await self._set(active_map=request.params["value"])
        elif name == CommandName.SET_SETTING:
            key = request.params["key"]
            old = self.snapshot.settings.get(key)
            if old is None:
                raise UnsupportedError("Šī funkcija nav pieejama.")
            settings = dict(self.snapshot.settings)
            settings[key] = replace(old, value=request.params["value"])
            await self._set(settings=settings)
        elif name == CommandName.REFRESH_MAP:
            await self._set(map_updated=datetime.now(UTC))
        # LOCATE and EMPTY_DUSTBIN have no visible state change

    async def get_map_svg(self) -> bytes | None:
        return DEMO_SVG

    async def diagnostics(self) -> dict[str, Any]:
        return {"integration": "demo", "note": "Simulēts robots. Dati nav īsti."}

    async def speech_targets(self) -> SpeechTargets:
        return SpeechTargets(("tts.demo",), ("media_player.demo",), ("notify.demo",))

    async def speak(
        self, tts_entity: str, media_player: str, message: str, language: str | None,
        volume: float | None,
    ) -> None:
        self.spoken.append(message)

    async def notify(self, service: str, message: str) -> None:
        self.spoken.append(message)
