"""The direct Ecovacs cloud adapter, using the real X9 PRO OMNI capability profile."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
    CachedMapInfoEvent,
    ChildLockEvent,
    ErrorEvent,
    FanSpeedEvent,
    FanSpeedLevel,
    RoomsEvent,
    StateEvent,
    StationEvent,
    StatsEvent,
    VolumeEvent,
    WorkMode,
    WorkModeEvent,
    station,
)
from deebot_client.events.map import Map as MapInfo
from deebot_client.events.water_info import WaterCustomAmountEvent
from deebot_client.hardware import ilt3k8
from deebot_client.models import DeviceInfo, Room, State
from deebot_client.rs.map import RotationAngle

from app.adapters.base import NotConnectedError
from app.adapters.ecovacs import STATE_FILE, EcovacsAdapter, _Store, build_snapshot, choose_device
from app.config import Settings
from app.models import Activity, CommandName, CommandRequest

CAPS = ilt3k8.get_device_info().capabilities


def events(*items: Any) -> Any:
    by_type = {type(e): e for e in items}
    return lambda t: by_type.get(t)


def full_events() -> Any:
    return events(
        AvailabilityEvent(available=True),
        StateEvent(State.DOCKED),
        BatteryEvent(93),
        FanSpeedEvent(FanSpeedLevel.MAX),
        WorkModeEvent(WorkMode.VACUUM_AND_MOP),
        RoomsEvent("m1", [Room("Virtuve", 2, ""), Room("", 1, "")]),
        CachedMapInfoEvent({
            MapInfo("m1", "Pirmais", True, True, RotationAngle.DEG_0),
            MapInfo("m2", "Otrais", False, True, RotationAngle.DEG_0),
        }),
        StationEvent(station.State.EMPTYING_DUSTBIN),
        StatsEvent(12, 1500, "auto"),
        ErrorEvent(0, "NoError"),
        ChildLockEvent(True),
        VolumeEvent(7, 10),
        WaterCustomAmountEvent(30),
    )


def test_snapshot_maps_events():
    snap = build_snapshot(CAPS, full_events(), connected=True, robot_name="Robis", model="X9")
    assert snap.robot_available and snap.activity == Activity.DOCKED and snap.battery == 93
    assert snap.fan_speed == "max" and "max_plus" in snap.fan_speed_options
    assert snap.work_mode == "vacuum_and_mop" and "mop_after_vacuum" in snap.work_mode_options
    assert [(r.id, r.name) for r in snap.rooms] == [("1", "Telpa 1"), ("2", "Virtuve")]
    assert snap.active_map == "Pirmais" and set(snap.map_options) == {"Pirmais", "Otrais"}
    assert snap.station_state == "emptying_dustbin"
    assert snap.last_clean_area == 12 and snap.last_clean_minutes == 25
    assert snap.error is None
    assert snap.settings["child_lock"].value is True
    assert (snap.settings["volume"].value, snap.settings["volume"].max) == (7, 10)
    water = snap.settings["water_amount"]
    assert (water.kind, water.value, water.min, water.max) == ("number", 30, 0, 50)
    caps = snap.capabilities
    assert caps["clean_rooms"] and caps["active_map"] and caps["empty_dustbin"] and caps["map"]
    assert caps["announcements"] is False


def test_snapshot_offline_and_errors():
    snap = build_snapshot(CAPS, events(), connected=False, problem="nav")
    assert not snap.backend_connected and snap.connection_problem == "nav"
    snap = build_snapshot(CAPS, events(AvailabilityEvent(available=False)), connected=True)
    assert not snap.robot_available and "nav sasniedzams" in snap.connection_problem
    snap = build_snapshot(CAPS, events(AvailabilityEvent(available=True), StateEvent(State.ERROR),
                                       ErrorEvent(102, "HostHang")), connected=True)
    assert snap.activity == Activity.ERROR and snap.error and snap.error.code == 102


def _info(**api: str) -> DeviceInfo:
    return DeviceInfo({"did": "d", "class": "ilt3k8", "company": "eco-ng", "name": "n", "resource": "r", **api},
                      ilt3k8.get_device_info())


def test_choose_device():
    a, b = _info(did="A", nick="Augšā"), _info(did="B", deviceName="DEEBOT X9 PRO OMNI")
    assert choose_device([a, b], "") is a
    assert choose_device([a, b], "augšā") is a
    assert choose_device([a, b], "deebot x9 pro omni") is b
    assert choose_device([a, b], "nav") is None


def test_store_keeps_device_id_and_drops_other_accounts_token(tmp_path):
    from deebot_client.models import AccountCredentials

    s = _Store(tmp_path / STATE_FILE, "a@b.lv")
    s.save_account(AccountCredentials("tok", "uid"))
    again = _Store(tmp_path / STATE_FILE, "A@B.lv ")
    assert again.device_id == s.device_id and again.account == AccountCredentials("tok", "uid")
    other = _Store(tmp_path / STATE_FILE, "c@d.lv")
    assert other.device_id == s.device_id and other.account is None
    assert "tok" not in (tmp_path / STATE_FILE).read_text()
    assert "a@b.lv" not in json.dumps(json.loads((tmp_path / STATE_FILE).read_text()))


class FakeBus:
    def __init__(self, last: Any) -> None:
        self._last = last
        self.refreshed: list[type] = []

    def get_last_event(self, t: type) -> Any:
        return self._last(t)

    def request_refresh(self, t: type) -> None:
        self.refreshed.append(t)


@pytest.fixture
def adapter(tmp_path) -> tuple[EcovacsAdapter, list[Any]]:
    settings = Settings.from_env({
        "ECOVACS_USERNAME": "a@b.lv", "ECOVACS_PASSWORD": "pw", "AUTH_DISABLED": "1",
        "DATA_DIR": str(tmp_path),
    })
    a = EcovacsAdapter(settings)
    sent: list[Any] = []

    async def execute(cmd: Any) -> dict[str, Any]:
        sent.append(cmd)
        return {}

    a._device = SimpleNamespace(  # type: ignore[assignment]
        capabilities=CAPS, events=FakeBus(full_events()), execute_command=execute,
        device_info={"deviceName": "X9"}, map=None,
    )
    return a, sent


async def test_send_maps_commands(adapter):
    a, sent = adapter
    await a.send(CommandRequest(CommandName.START))
    await a.send(CommandRequest(CommandName.CLEAN_ROOMS, {"rooms": ["1", "2"], "cleanings": 2}))
    await a.send(CommandRequest(CommandName.CLEAN_ZONE, {"coordinates": [-10, 0, 500, 600]}))
    await a.send(CommandRequest(CommandName.SET_FAN_SPEED, {"value": "max_plus"}))
    await a.send(CommandRequest(CommandName.SET_WORK_MODE, {"value": "mop_after_vacuum"}))
    await a.send(CommandRequest(CommandName.SET_ACTIVE_MAP, {"value": "Otrais"}))
    await a.send(CommandRequest(CommandName.SET_SETTING, {"key": "child_lock", "value": False}))
    await a.send(CommandRequest(CommandName.SET_SETTING, {"key": "water_amount", "value": 40}))
    await a.send(CommandRequest(CommandName.EMPTY_DUSTBIN))
    await a.send(CommandRequest(CommandName.RETURN_TO_BASE))
    names = [type(c).__name__ for c in sent]
    assert names == [
        "CleanV2", "CleanArea", "CleanArea", "SetFanSpeed", "SetWorkMode", "SetMajorMap",
        "SetChildLock", "SetWaterInfo", "StationAction", "Charge",
    ]
    assert sent[1]._args["type"] == "spotArea" and sent[1]._args["content"] == "1,2"
    assert sent[1]._args["count"] == 2
    assert sent[2]._args["type"] == "customArea" and sent[2]._args["content"] == "-10,0,500,600"
    assert sent[5]._args == {"mid": "m2"}


async def test_send_without_connection(tmp_path):
    settings = Settings.from_env({
        "ECOVACS_USERNAME": "a@b.lv", "ECOVACS_PASSWORD": "pw", "AUTH_DISABLED": "1",
        "DATA_DIR": str(tmp_path),
    })
    with pytest.raises(NotConnectedError):
        await EcovacsAdapter(settings).send(CommandRequest(CommandName.START))
