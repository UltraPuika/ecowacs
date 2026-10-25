"""Entity discovery and snapshot building from Home Assistant data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.adapters.homeassistant import build_snapshot, discover, parse_rooms
from app.models import Activity

DID = "E0001234567890"


def reg(entity_id: str, key: str | None, disabled: str | None = None, device: str = "dev1") -> dict:
    unique = DID if key is None else f"{DID}_{key}"
    return {
        "entity_id": entity_id, "platform": "ecovacs", "device_id": device,
        "unique_id": unique, "disabled_by": disabled,
    }


REGISTRY = [
    reg("vacuum.robots", None),
    reg("sensor.robots_battery", "battery_level"),
    reg("sensor.robots_error", "error", disabled="integration"),
    reg("sensor.robots_area", "stats_area"),
    reg("sensor.robots_time", "stats_time"),
    reg("select.robots_work_mode", "work_mode"),
    reg("select.robots_map", "active_map"),
    reg("image.robots_map", "map"),
    reg("event.robots_last_job", "stats_report"),
    reg("switch.robots_carpet", "carpet_auto_fan_boost"),
    reg("number.robots_volume", "volume"),
    {"entity_id": "sensor.other", "platform": "other", "device_id": "dev1", "unique_id": "x_battery_level"},
    reg("vacuum.other_robot", None, device="dev2"),
]


def st(entity_id: str, state: str, attrs: dict | None = None, age: int = 5) -> dict:
    t = (datetime.now(UTC) - timedelta(seconds=age)).isoformat()
    return {"entity_id": entity_id, "state": state, "attributes": attrs or {},
            "last_updated": t, "last_reported": t}


def states() -> dict[str, dict]:
    items = [
        st("vacuum.robots", "cleaning", {
            "supported_features": 4 | 8 | 16 | 32 | 256 | 512 | 8192,
            "fan_speed": "normal", "fan_speed_list": ["quiet", "normal", "max", "max_plus"],
            "rooms": {"Virtuve": 1, "Guļamistaba": [2, 5]},
        }),
        st("sensor.robots_battery", "64"),
        st("sensor.robots_area", "12"),
        st("sensor.robots_time", "1800", {"unit_of_measurement": "s"}),
        st("select.robots_work_mode", "vacuum_and_mop",
           {"options": ["vacuum", "vacuum_and_mop", "mop_after_vacuum"]}),
        st("select.robots_map", "Stāvs 1", {"options": ["Stāvs 1"]}),
        st("image.robots_map", "2026-10-25T10:00:00+00:00"),
        st("switch.robots_carpet", "on"),
        st("number.robots_volume", "7", {"min": 0, "max": 10, "step": 1}),
    ]
    return {i["entity_id"]: i for i in items}


def test_discovery_uses_registry_not_guesses():
    d = discover(REGISTRY)
    assert d.vacuum == "vacuum.other_robot"  # deterministic: first by entity ID
    d = discover(REGISTRY, "vacuum.robots")
    assert d.roles["battery"] == "sensor.robots_battery"
    assert d.roles["last_job"] == "event.robots_last_job"
    assert d.disabled == {"error": "sensor.robots_error"}
    assert "sensor.other" not in d.entity_ids()
    assert d.candidates == ["vacuum.other_robot", "vacuum.robots"]


def test_discovery_reports_missing_robot():
    d = discover([], "")
    assert d.vacuum is None and "Ecovacs" in d.problem
    d = discover(REGISTRY, "vacuum.nav_tada")
    assert d.vacuum is None and "HA_VACUUM_ENTITY" in d.problem


def test_rooms_with_duplicate_names_are_flattened():
    rooms = parse_rooms({"Virtuve": 1, "Guļamistaba": [2, 5]})
    assert [(r.id, r.name) for r in rooms] == [
        ("1", "Virtuve"), ("2", "Guļamistaba (1)"), ("5", "Guļamistaba (2)"),
    ]
    assert parse_rooms(None) == ()


def test_snapshot_from_states():
    d = discover(REGISTRY, "vacuum.robots")
    snap = build_snapshot(d, states(), connected=True, device={"name": "Robis", "model": "DEEBOT X9 PRO OMNI"})
    assert snap.activity == Activity.CLEANING
    assert snap.battery == 64
    assert snap.robot_available
    assert snap.work_mode == "vacuum_and_mop"
    assert snap.last_clean_minutes == 30
    assert snap.settings["carpet_auto_fan_boost"].value is True
    assert snap.settings["volume"].max == 10
    assert snap.capabilities["clean_rooms"] and snap.capabilities["start"]
    assert snap.capabilities["error_codes"] is False  # sensor disabled in HA
    assert snap.model == "DEEBOT X9 PRO OMNI"
    assert snap.last_update is not None


def test_unavailable_robot():
    d = discover(REGISTRY, "vacuum.robots")
    s = states()
    s["vacuum.robots"]["state"] = "unavailable"
    snap = build_snapshot(d, s, connected=True)
    assert not snap.robot_available
    assert snap.connection_problem == "Home Assistant nevar sazināties ar robotu."


def test_disconnected_ha():
    d = discover(REGISTRY, "vacuum.robots")
    snap = build_snapshot(d, states(), connected=False, connection_problem="x")
    assert not snap.backend_connected
    assert snap.battery is None  # never show cached values as current


def test_error_sensor_translated():
    registry = [r for r in REGISTRY if r["entity_id"] != "sensor.robots_error"]
    registry.append(reg("sensor.robots_error", "error"))
    d = discover(registry, "vacuum.robots")
    s = states()
    s["sensor.robots_error"] = st("sensor.robots_error", "105", {"description": "Stuck"})
    snap = build_snapshot(d, s, connected=True)
    assert snap.error.title == "Robots ir iestrēdzis"
    s["sensor.robots_error"] = st("sensor.robots_error", "0")
    assert build_snapshot(d, s, connected=True).error is None


def test_error_state_without_code_is_generic():
    d = discover(REGISTRY, "vacuum.robots")
    s = states()
    s["vacuum.robots"]["state"] = "error"
    snap = build_snapshot(d, s, connected=True)
    assert snap.activity == Activity.ERROR
    assert snap.error.title == "Nepieciešama uzmanība"
