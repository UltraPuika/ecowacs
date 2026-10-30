"""Direct mode against the REAL deebot-client objects (a real Device with the X9 profile).

Only the network is replaced: ``Device._execute_command`` is stubbed so that no
request ever leaves the machine. Skipped when deebot-client is not installed
(it needs Python 3.14).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import aiohttp
import pytest

pytest.importorskip("deebot_client")

from deebot_client.authentication import Authenticator, create_rest_config  # noqa: E402
from deebot_client.command import DeviceCommandResult  # noqa: E402
from deebot_client.device import Device  # noqa: E402
from deebot_client.events import (  # noqa: E402
    AvailabilityEvent,
    BatteryEvent,
    CleanJobStatus,
    ErrorEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    ReportStatsEvent,
    RoomsEvent,
    StateEvent,
    StatsEvent,
    VolumeEvent,
    WorkMode,
    WorkModeEvent,
)
from deebot_client.events.map import CachedMapInfoEvent, Map  # noqa: E402
from deebot_client.events.station import State as StationState  # noqa: E402
from deebot_client.events.station import StationEvent  # noqa: E402
from deebot_client.exceptions import AuthenticationError  # noqa: E402
from deebot_client.hardware import get_static_device_info  # noqa: E402
from deebot_client.models import AccountCredentials, DeviceInfo, Room, State  # noqa: E402
from deebot_client.util import md5  # noqa: E402

import app.adapters.direct as direct  # noqa: E402
from app.adapters.base import AdapterError, UnsupportedError  # noqa: E402
from app.adapters.direct import DirectAdapter, DirectProblem, Link, choose_device, numbered_rooms  # noqa: E402
from app.config import Settings  # noqa: E402
from app.ecovacs_session import StoredSession, save_session  # noqa: E402
from app.models import Activity, CommandName, CommandRequest  # noqa: E402

API_INFO = {
    "class": "ilt3k8", "company": "eco-ng", "deviceName": "DEEBOT X9 PRO OMNI",
    "did": "did-123", "name": "E0000-internal", "nick": "Robis", "resource": "r",
}


class Cloud:
    """Stands in for the cloud: records commands, answers like a reachable robot."""

    def __init__(self) -> None:
        self.commands: list[Any] = []
        self.reachable = True

    async def execute(self, _device: Device, command: Any) -> DeviceCommandResult:
        self.commands.append(command)
        if self.reachable:
            return DeviceCommandResult(device_reached=True, raw_response={"ret": "ok"})
        return DeviceCommandResult(device_reached=False)

    def sent(self, name: str) -> list[Any]:
        return [c for c in self.commands if getattr(c, "NAME", type(c).__name__) == name]


@pytest.fixture
def cloud(monkeypatch) -> Cloud:
    c = Cloud()

    async def fake(self: Device, command: Any) -> DeviceCommandResult:
        return await c.execute(self, command)

    monkeypatch.setattr(Device, "_execute_command", fake)
    monkeypatch.setattr(direct, "HEARTBEAT_SECONDS", 3600.0)
    monkeypatch.setattr(direct, "MIN_RETRY", 0.05)
    return c


class FakeConnector:
    def __init__(self) -> None:
        self.calls = 0
        self.errors: list[BaseException] = []
        self.http: aiohttp.ClientSession | None = None
        self.closed = 0

    async def connect(self, stored: StoredSession, wanted: str) -> Link:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        self.http = aiohttp.ClientSession()
        auth = Authenticator(
            create_rest_config(self.http, device_id=stored.device_id, alpha_2_country=stored.country),
            "", md5(""), account_credentials=AccountCredentials("tok", "uid"),
        )
        static = await get_static_device_info("ilt3k8")
        assert static is not None, "the X9 PRO OMNI profile must exist in the library"
        device = Device(DeviceInfo(API_INFO, static), auth)  # type: ignore[arg-type]

        async def close() -> None:
            self.closed += 1
            await device.teardown()
            await self.http.close()  # type: ignore[union-attr]

        return Link(device, close, [{"name": "Robis", "model": "DEEBOT X9 PRO OMNI", "class": "ilt3k8"}])


def make_settings(tmp_path, **extra: str) -> Settings:
    return Settings.from_env({"MODE": "direct", "AUTH_DISABLED": "1", "DATA_DIR": str(tmp_path), **extra})


async def until(predicate, timeout: float = 3.0) -> None:
    end = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > end:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


@pytest.fixture
async def adapter(tmp_path, cloud):
    save_session(tmp_path, StoredSession("DEV12345", "LV", "uid", "tok"))
    connector = FakeConnector()
    a = DirectAdapter(make_settings(tmp_path), connector)  # type: ignore[arg-type]
    a.connector = connector  # type: ignore[attr-defined]
    await a.start()
    await until(lambda: a.snapshot.backend_connected)
    yield a
    await a.stop()


def device_of(adapter: DirectAdapter) -> Device:
    assert adapter._link is not None
    return adapter._link.device


# --- connecting and showing the robot ----------------------------------------------
async def test_connects_and_reports_robot_identity(adapter):
    await until(lambda: adapter.snapshot.robot_available)  # first answer proves reachability
    snap = adapter.snapshot
    assert snap.robot_name == "Robis" and snap.model == "DEEBOT X9 PRO OMNI"
    assert snap.last_update is not None
    assert snap.capabilities["announcements"] is False
    assert snap.capabilities["clean_rooms"] is False  # no rooms known yet
    assert snap.demo is False


async def test_events_become_snapshot(adapter):
    bus = device_of(adapter).events
    await until(lambda: adapter.snapshot.robot_available)
    bus.notify(StateEvent(State.CLEANING))
    bus.notify(BatteryEvent(64))
    bus.notify(FanSpeedEvent(FanSpeedLevel.MAX))
    bus.notify(WorkModeEvent(WorkMode.VACUUM_AND_MOP))
    bus.notify(StatsEvent(area=12, time=1800, type="auto"))
    bus.notify(StationEvent(StationState.WASHING_MOP))
    bus.notify(VolumeEvent(volume=7, maximum=10))
    bus.notify(RoomsEvent("m1", [Room("Gaitenis", 4, ""), Room("Virtuve", 12, "")]))
    await until(lambda: adapter.snapshot.rooms and adapter.snapshot.battery == 64
                and adapter.snapshot.settings.get("volume"))
    snap = adapter.snapshot
    assert snap.activity == Activity.CLEANING
    assert (snap.fan_speed, snap.work_mode) == ("max", "vacuum_and_mop")
    assert snap.fan_speed_options == ("quiet", "normal", "max", "max_plus")
    assert snap.work_mode_options == ("mop_after_vacuum", "vacuum", "vacuum_and_mop")
    assert (snap.last_clean_area, snap.last_clean_minutes) == (12.0, 30.0)
    assert snap.station_state == "washing_mop"
    assert snap.settings["volume"].value == 7 and snap.settings["volume"].max == 10
    assert [(r.id, r.name) for r in snap.rooms] == [("4", "Gaitenis"), ("12", "Virtuve")]
    assert snap.capabilities["clean_rooms"] is True


async def test_error_event_is_translated(adapter):
    bus = device_of(adapter).events
    bus.notify(ErrorEvent(105, "Stuck"))
    await until(lambda: adapter.snapshot.error is not None)
    assert adapter.snapshot.error.title == "Robots ir iestrēdzis"
    bus.notify(ErrorEvent(0, "NoError"))
    await until(lambda: adapter.snapshot.error is None)


async def test_maps_and_active_map(adapter):
    from deebot_client.rs.map import RotationAngle  # type: ignore[import-not-found]

    bus = device_of(adapter).events
    bus.notify(CachedMapInfoEvent({
        Map("1", "Pirmais stāvs", True, True, RotationAngle.DEG_0),
        Map("2", "", False, True, RotationAngle.DEG_0),
    }))
    await until(lambda: adapter.snapshot.map_options)
    snap = adapter.snapshot
    assert snap.active_map == "Pirmais stāvs"
    assert set(snap.map_options) == {"Pirmais stāvs", "Karte 2"}
    assert snap.capabilities["active_map"] is True


async def test_job_finished_event_emitted_only_when_finished(adapter):
    seen: list[tuple[str, dict]] = []
    adapter.add_event_listener(lambda name, data: seen.append((name, data)))
    bus = device_of(adapter).events
    bus.notify(ReportStatsEvent(area=5, time=60, type="auto", cleaning_id="a", status=CleanJobStatus.CLEANING, content=[]))
    await asyncio.sleep(0.05)
    assert seen == []
    bus.notify(ReportStatsEvent(area=6, time=70, type="auto", cleaning_id="b", status=CleanJobStatus.FINISHED, content=[]))
    await until(lambda: seen)
    assert seen == [("job_finished", {"result": "finished"})]


async def test_unavailable_event_marks_robot_unreachable(adapter):
    await until(lambda: adapter.snapshot.robot_available)
    device_of(adapter).events.notify(AvailabilityEvent(available=False))
    await until(lambda: not adapter.snapshot.robot_available)
    assert "nevar sazināties" in adapter.snapshot.connection_problem


# --- commands reach the library correctly ---------------------------------------------
async def send(adapter, name: CommandName, **params):
    await adapter.send(CommandRequest(name, params))


async def test_basic_commands(adapter, cloud):
    await send(adapter, CommandName.START)
    await send(adapter, CommandName.PAUSE)
    await send(adapter, CommandName.RESUME)
    await send(adapter, CommandName.STOP)
    await send(adapter, CommandName.RETURN_TO_BASE)
    await send(adapter, CommandName.LOCATE)
    acts = [c._args.get("act") for c in cloud.commands if getattr(c, "NAME", "") == "clean_V2"]
    assert acts == ["start", "pause", "resume", "stop"]
    assert cloud.sent("charge")[-1]._args == {"act": "go"} and cloud.sent("playSound")


async def test_room_ids_are_sent_as_a_list_not_split_per_character(adapter, cloud):
    await send(adapter, CommandName.CLEAN_ROOMS, rooms=["12", "3"], cleanings=2)
    # "12,3" - a pre-joined string would have become "1,2,,,3"
    assert cloud.sent("clean")[-1]._args == {"act": "start", "type": "spotArea", "content": "12,3", "count": 2}


async def test_zone_command(adapter, cloud):
    await send(adapter, CommandName.CLEAN_ZONE, coordinates=[-10, 20, 300, 400], cleanings=1)
    assert cloud.sent("clean")[-1]._args == {
        "act": "start", "type": "customArea", "content": "-10,20,300,400", "count": 1,
    }


async def test_settings_commands(adapter, cloud):
    await send(adapter, CommandName.SET_FAN_SPEED, value="max_plus")
    assert cloud.sent("setSpeed")[-1]._args == {"speed": 2}
    await send(adapter, CommandName.SET_WORK_MODE, value="mop_after_vacuum")
    await send(adapter, CommandName.SET_SETTING, key="child_lock", value=True)
    await send(adapter, CommandName.SET_SETTING, key="volume", value=4)
    assert cloud.sent("setVolume")[-1]._args == {"volume": 4}
    await send(adapter, CommandName.SET_SETTING, key="water_amount", value=20)
    await send(adapter, CommandName.SET_SETTING, key="carpet_auto_fan_boost", value=False)
    names = {getattr(c, "NAME", type(c).__name__) for c in cloud.commands}
    assert {"setSpeed", "setWorkMode", "setChildLock", "setVolume", "setWaterInfo", "setCarpertPressure"} <= names


async def test_unknown_setting_is_unsupported(adapter):
    with pytest.raises(UnsupportedError):
        await send(adapter, CommandName.SET_SETTING, key="nonsense", value=1)


async def test_unreachable_robot_command_fails_clearly(adapter, cloud):
    await until(lambda: adapter.snapshot.robot_available)
    cloud.reachable = False
    device_of(adapter).events.notify(AvailabilityEvent(available=False))
    await until(lambda: not adapter.snapshot.robot_available)
    with pytest.raises(AdapterError) as err:
        await send(adapter, CommandName.START)
    assert "nav sasniedzams" in err.value.user_message


async def test_empty_answer_with_unknown_reachability_is_left_to_state_verification(adapter, cloud):
    cloud.reachable = False  # library hides failures behind an empty answer
    adapter._available = None
    await send(adapter, CommandName.START)  # must not raise: verification decides
    assert cloud.sent("clean_V2")


async def test_map_is_none_until_the_robot_sends_one(adapter):
    assert await adapter.get_map_svg() is None


# --- heartbeat, problems and retries ----------------------------------------------------
async def test_heartbeat_refreshes_last_update(tmp_path, cloud, monkeypatch):
    monkeypatch.setattr(direct, "HEARTBEAT_SECONDS", 0.05)
    save_session(tmp_path, StoredSession("DEV12345", "LV", "uid", "tok"))
    a = DirectAdapter(make_settings(tmp_path), FakeConnector())  # type: ignore[arg-type]
    await a.start()
    try:
        await until(lambda: a.snapshot.last_update is not None)
        first = a.snapshot.last_update
        await until(lambda: a.snapshot.last_update > first)
        assert len(cloud.sent("getBattery")) >= 2
    finally:
        await a.stop()


async def test_no_saved_login_stops_with_instructions_and_never_connects(tmp_path, cloud):
    connector = FakeConnector()
    a = DirectAdapter(make_settings(tmp_path), connector)  # type: ignore[arg-type]
    await a.start()
    await until(lambda: a.snapshot.connection_problem)
    assert "ecovacs_login" in a.snapshot.connection_problem
    await asyncio.sleep(0.2)
    assert connector.calls == 0 and not a.snapshot.backend_connected
    await a.stop()


async def test_authentication_failure_is_not_retried(tmp_path, cloud):
    save_session(tmp_path, StoredSession("DEV12345", "LV", "uid", "tok"))
    connector = FakeConnector()
    connector.errors = [AuthenticationError("bad token")]
    a = DirectAdapter(make_settings(tmp_path), connector)  # type: ignore[arg-type]
    await a.start()
    await until(lambda: a.snapshot.connection_problem)
    await asyncio.sleep(0.3)
    assert connector.calls == 1, "a rejected login must never be retried automatically"
    assert "ecovacs_login" in a.snapshot.connection_problem
    await a.stop()


async def test_unsupported_robot_is_a_final_problem(tmp_path, cloud):
    save_session(tmp_path, StoredSession("DEV12345", "LV", "uid", "tok"))
    connector = FakeConnector()
    connector.errors = [DirectProblem("Ecovacs bibliotēka vēl neatbalsta šo robota modeli.")]
    a = DirectAdapter(make_settings(tmp_path), connector)  # type: ignore[arg-type]
    await a.start()
    await until(lambda: a.snapshot.connection_problem)
    await asyncio.sleep(0.2)
    assert connector.calls == 1 and "neatbalsta" in a.snapshot.connection_problem
    await a.stop()


async def test_network_errors_are_retried_then_recover(tmp_path, cloud):
    save_session(tmp_path, StoredSession("DEV12345", "LV", "uid", "tok"))
    connector = FakeConnector()
    connector.errors = [OSError("down"), TimeoutError()]
    a = DirectAdapter(make_settings(tmp_path), connector)  # type: ignore[arg-type]
    await a.start()
    try:
        await until(lambda: a.snapshot.backend_connected, timeout=5)
        assert connector.calls == 3
    finally:
        await a.stop()


async def test_rediscover_picks_up_a_login_saved_later(tmp_path, cloud):
    connector = FakeConnector()
    a = DirectAdapter(make_settings(tmp_path), connector)  # type: ignore[arg-type]
    await a.start()
    await until(lambda: a.snapshot.connection_problem)
    save_session(tmp_path, StoredSession("DEV12345", "LV", "uid", "tok"))
    await a.rediscover()
    try:
        await until(lambda: a.snapshot.backend_connected)
    finally:
        await a.stop()


async def test_stop_closes_the_connection(adapter):
    connector = adapter.connector
    await adapter.stop()
    assert connector.closed == 1 and not adapter.snapshot.backend_connected


async def test_diagnostics_contain_no_secrets(adapter, tmp_path):
    text = str(await adapter.diagnostics())
    assert "tok" not in text
    assert "uid" not in text and "DEV12345" not in text and "did-123" not in text
    assert "ilt3k8" in text and "deebot-client" in text


# --- pure helpers -------------------------------------------------------------------------
def info(nick: str, did: str = "d") -> SimpleNamespace:
    return SimpleNamespace(api={"nick": nick, "name": nick, "did": did})


def test_choose_device():
    a, b = info("B-robot", "2"), info("A-robot", "1")
    assert choose_device([a, b], [], [], "") is b  # deterministic: first by name
    assert choose_device([a, b], [], [], "b-ROBOT") is a
    assert choose_device([a, b], [], [], "1") is b  # by id
    with pytest.raises(DirectProblem, match="ECOVACS_DEVICE"):
        choose_device([a], [], [], "nope")
    with pytest.raises(DirectProblem, match="vecāku"):
        choose_device([], [{"x": 1}], [], "")
    with pytest.raises(DirectProblem, match="neatbalsta"):
        choose_device([], [], [{"x": 1}], "")
    with pytest.raises(DirectProblem, match="nav neviena"):
        choose_device([], [], [], "")


def test_numbered_rooms():
    rooms = numbered_rooms([Room("Guļamistaba", 5, ""), Room("Virtuve", 2, ""), Room("Guļamistaba", 9, ""), Room("", 1, "")])
    assert [(r.id, r.name) for r in rooms] == [
        ("1", "Telpa 1"), ("2", "Virtuve"), ("5", "Guļamistaba (1)"), ("9", "Guļamistaba (2)"),
    ]


# --- through the real HTTP app ---------------------------------------------------------
def test_api_in_direct_mode_before_login(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.storage import Storage

    settings = make_settings(tmp_path)
    adapter = DirectAdapter(settings, FakeConnector())  # type: ignore[arg-type]
    with TestClient(create_app(settings, adapter, Storage(":memory:"))) as client:
        for _ in range(100):
            data = client.get("/api/status").json()
            if data["robot"]["connection_problem"]:
                break
        assert data["mode"] == "direct" and data["robot"]["backend_connected"] is False
        assert "ecovacs_login" in data["robot"]["connection_problem"]
        assert data["freshness"]["stale"] is True
        assert "Ecovacs serveri" in data["freshness"]["reason"]
        assert "Home Assistant" not in data["freshness"]["reason"]
        diag = client.get("/api/diagnostics").json()["adapter"]
        assert diag["integration"] == "direct" and diag["login_saved"] is False
        # commands are refused, not faked
        result = client.post("/api/commands", json={"name": "start"}, headers={"X-Requested-With": "deebot-lv"}).json()
        assert result["status"] == "rejected"
