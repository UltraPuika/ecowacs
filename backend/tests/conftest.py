"""Shared test fixtures. No physical robot or Home Assistant is needed."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.adapters.base import AdapterError, RobotAdapter
from app.config import Settings
from app.models import Activity, CommandName, CommandRequest, RobotSnapshot, Room, Setting

ALL_CAPS = {
    k: True
    for k in (
        "start", "pause", "stop", "return_to_base", "locate", "fan_speed", "clean_rooms",
        "clean_zone", "work_mode", "active_map", "map", "error_codes", "job_finished_event",
        "empty_dustbin", "announcements",
    )
}


def make_snapshot(**changes: Any) -> RobotSnapshot:
    base = RobotSnapshot(
        backend_connected=True,
        robot_available=True,
        activity=Activity.DOCKED,
        battery=80,
        fan_speed="normal",
        fan_speed_options=("quiet", "normal", "max", "max_plus"),
        work_mode="vacuum",
        work_mode_options=("vacuum", "vacuum_and_mop", "mop_after_vacuum"),
        rooms=(Room("1", "Virtuve"), Room("2", "Gaitenis")),
        active_map="Stāvs 1",
        map_options=("Stāvs 1", "Stāvs 2"),
        settings={
            "child_lock": Setting("child_lock", "switch", False),
            "volume": Setting("volume", "number", 5, 0, 10, 1),
        },
        capabilities=dict(ALL_CAPS),
        last_update=datetime.now(UTC),
    )
    return replace(base, **changes)


class FakeAdapter(RobotAdapter):
    """Controllable adapter. ``reaction`` decides what state a command leads to."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[CommandRequest] = []
        self.fail_with: AdapterError | None = None
        self.send_delay = 0.0
        self.react = True
        self.svg: bytes | None = b"<svg xmlns='http://www.w3.org/2000/svg'/>"
        self.spoken: list[tuple[str, str, str]] = []
        self.notified: list[tuple[str, str]] = []
        self.speak_error: AdapterError | None = None

    async def start(self) -> None:
        await self._publish(make_snapshot())

    async def stop(self) -> None:
        pass

    async def set(self, **changes: Any) -> None:
        await self._publish(replace(self.snapshot, **changes))

    async def emit(self, name: str, data: dict[str, Any]) -> None:
        await self._emit(name, data)

    async def send(self, request: CommandRequest) -> None:
        self.sent.append(request)
        if self.send_delay:
            await asyncio.sleep(self.send_delay)
        if self.fail_with:
            raise self.fail_with
        if not self.react:
            return
        target = {
            CommandName.START: Activity.CLEANING,
            CommandName.CLEAN_ROOMS: Activity.CLEANING,
            CommandName.RESUME: Activity.CLEANING,
            CommandName.PAUSE: Activity.PAUSED,
            CommandName.STOP: Activity.IDLE,
            CommandName.RETURN_TO_BASE: Activity.RETURNING,
        }.get(request.name)
        if target:
            asyncio.get_running_loop().call_later(
                0.01, lambda: asyncio.ensure_future(self.set(activity=target))
            )
        if request.name == CommandName.SET_FAN_SPEED:
            await self.set(fan_speed=request.params["value"])

    async def get_map_svg(self) -> bytes | None:
        return self.svg

    async def diagnostics(self) -> dict[str, Any]:
        return {"integration": "fake", "ha_url": "http://ha.local:8123",
                "note": "Authorization: Bearer abc.def-secret-token"}

    async def speak(self, tts_entity: str, media_player: str, message: str,
                    language: str | None, volume: float | None) -> None:
        if self.speak_error:
            raise self.speak_error
        self.spoken.append((tts_entity, media_player, message))

    async def notify(self, service: str, message: str) -> None:
        self.notified.append((service, message))


@pytest.fixture
def fake_adapter() -> FakeAdapter:
    return FakeAdapter()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings.from_env(
        {
            "MODE": "homeassistant",
            "HA_URL": "http://ha.local:8123",
            "HA_TOKEN": "super-secret-ha-token-123",
            "APP_PASSWORD": "parole123",
            "DATA_DIR": str(tmp_path),
            "VERIFY_TIMEOUT": "0.5",
            "COMMAND_TIMEOUT": "0.5",
            "DEDUPE_WINDOW": "1",
        }
    )
