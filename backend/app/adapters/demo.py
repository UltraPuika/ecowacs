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


# Same units as deebot-client's SVG: 1 unit = 50 mm, robot y axis points up.
_W, _H = 200, 130
# Rooms as (x1, y1, x2, y2) in SVG units.
_ROOMS = {
    "1": ("Viesistaba", (4, 4, 104, 72)),
    "2": ("Virtuve", (104, 4, 196, 58)),
    "3": ("Guļamistaba", (4, 72, 104, 126)),
    "4": ("Gaitenis", (104, 58, 196, 126)),
}


def _is_wall(x: int, y: int) -> bool:
    if x in (3, 4, _W - 5, _W - 4) or y in (3, 4, _H - 5, _H - 4):
        return True
    return (
        (x == 104 and not (25 <= y <= 36 or 60 <= y <= 70 or 95 <= y <= 107))
        or (y == 72 and x <= 104)
        or (y == 58 and x >= 104 and not 140 <= x <= 154)
    )


def _demo_map_png() -> bytes:
    pixels = []
    for y in range(_H):
        row = []
        for x in range(_W):
            if not (3 <= x <= _W - 4 and 3 <= y <= _H - 4):
                row.append(0)
            elif _is_wall(x, y):
                row.append(2)
            elif 22 <= x <= 62 and 22 <= y <= 50:
                row.append(3)  # a carpet in the living room
            else:
                row.append(1)
        pixels.append(row)
    return make_indexed_png(_W, _H, pixels, _PALETTE)


def _outline(box: tuple[int, int, int, int]) -> tuple[tuple[int, int], ...]:
    x1, y1, x2, y2 = box
    return tuple((x * 50, -y * 50) for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)))


DEMO_SVG = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_W} {_H}">'
    f'<image x="0" y="0" width="{_W}" height="{_H}" style="image-rendering: pixelated" '
    'href="data:image/png;base64,' + base64.b64encode(_demo_map_png()).decode() + '"/>'
    '<defs><radialGradient id="dbg" cx="50%" cy="50%" r="50%" fx="50%" fy="50%">'
    '<stop offset="70%" style="stop-color:#00f"/><stop offset="97%" style="stop-color:#00f0"/>'
    '</radialGradient><g id="d"><circle fill="url(#dbg)" r="5"/>'
    '<circle fill="blue" r="3.5" stroke="white" stroke-width="0.5"/></g>'
    '<g id="c"><path d="M4-6.4C4-4.2 0 0 0 0s-4-4.2-4-6.4 1.8-4 4-4 4 1.8 4 4z" fill="#ffe605"/>'
    '<circle cy="-6.4" fill="#fff" r="2.8"/></g></defs>'
    '<path fill="none" stroke="#fff" stroke-width="1.2" stroke-linejoin="round" '
    'd="M150 112V65H96V14H88V66H80V14H72V66H64V14"/>'
    '<g class="w"><path class="v" d="M20 110h40"/></g>'
    '<g class="w"><path class="n" d="M160 12h28v20h-28z"/></g>'
    '<use href="#c" x="150" y="124"/><use href="#d" x="150" y="114"/>'
    '<text x="100" y="68" font-size="10" font-weight="700" text-anchor="middle" '
    'fill="#6a1b9a" fill-opacity="0.25">DEMO</text>'
    "<style>path{stroke-width: 1.5; vector-effect: non-scaling-stroke}.w path{stroke-dasharray: 4}"
    ".v{stroke: #f00000; fill: #f0000030}.n{stroke: #ffa500; fill: #ffa50030}</style>"
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
                rooms=tuple(Room(rid, name, _outline(box)) for rid, (name, box) in _ROOMS.items()),
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

    def map_rotation(self) -> int | None:
        return 0

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
