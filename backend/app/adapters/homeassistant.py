"""Robot adapter that uses Home Assistant's official Ecovacs integration.

Entity IDs are never guessed. They are discovered from Home Assistant's entity
registry: every entity of the ``ecovacs`` platform that belongs to the same
device as the vacuum. Ecovacs unique IDs end with ``_<key>``, where ``key`` is
the entity-description key in ``homeassistant/components/ecovacs``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import aiohttp

from ..config import Settings
from ..errors_lv import GENERIC_ERROR, translate_error
from ..models import Activity, CommandName, CommandRequest, RobotSnapshot, Room, Setting
from .base import AdapterError, NotConnectedError, RobotAdapter, SpeechTargets, UnsupportedError
from .ha_client import HAConnection, HAError

_LOGGER = logging.getLogger(__name__)

# role -> (domain, entity description key)
ROLES: dict[str, tuple[str, str]] = {
    "battery": ("sensor", "battery_level"),
    "error": ("sensor", "error"),
    "stats_area": ("sensor", "stats_area"),
    "stats_time": ("sensor", "stats_time"),
    "station_state": ("sensor", "station_state"),
    "work_mode": ("select", "work_mode"),
    "active_map": ("select", "active_map"),
    "water_amount": ("number", "water_amount"),
    "clean_count": ("number", "clean_count"),
    "volume": ("number", "volume"),
    "carpet_auto_fan_boost": ("switch", "carpet_auto_fan_boost"),
    "continuous_cleaning": ("switch", "continuous_cleaning"),
    "child_lock": ("switch", "child_lock"),
    "map": ("image", "map"),
    "last_job": ("event", "stats_report"),
    "empty_dustbin": ("button", "station_action_empty_dustbin"),
}
# Entities that HA disables by default but that this app benefits from.
RECOMMENDED_ENABLED = ("error", "last_job", "carpet_auto_fan_boost", "continuous_cleaning")
SETTING_ROLES = (
    "carpet_auto_fan_boost",
    "continuous_cleaning",
    "child_lock",
    "water_amount",
    "clean_count",
    "volume",
)

# Vacuum entity feature flags (homeassistant/components/vacuum/const.py)
FEATURE_PAUSE = 4
FEATURE_STOP = 8
FEATURE_RETURN_HOME = 16
FEATURE_FAN_SPEED = 32
FEATURE_SEND_COMMAND = 256
FEATURE_LOCATE = 512
FEATURE_START = 8192

_ACTIVITY = {
    "cleaning": Activity.CLEANING,
    "paused": Activity.PAUSED,
    "returning": Activity.RETURNING,
    "docked": Activity.DOCKED,
    "idle": Activity.IDLE,
    "error": Activity.ERROR,
}
_UNAVAILABLE = {"unavailable", None}
_NO_VALUE = {"unavailable", "unknown", None, ""}


@dataclass
class Discovery:
    """Entities found for the robot."""

    vacuum: str | None = None
    device_id: str | None = None
    roles: dict[str, str] = field(default_factory=dict)  # role -> entity_id (enabled)
    disabled: dict[str, str] = field(default_factory=dict)  # role -> entity_id (disabled in HA)
    candidates: list[str] = field(default_factory=list)  # all ecovacs vacuums
    problem: str | None = None

    def entity_ids(self) -> set[str]:
        """All tracked entity IDs."""
        ids = set(self.roles.values())
        if self.vacuum:
            ids.add(self.vacuum)
        return ids


def discover(registry: list[dict[str, Any]], wanted_vacuum: str = "") -> Discovery:
    """Find the vacuum and its related entities in the entity registry."""
    result = Discovery()
    ecovacs = [e for e in registry if e.get("platform") == "ecovacs"]
    vacuums = [e for e in ecovacs if str(e.get("entity_id", "")).startswith("vacuum.")]
    result.candidates = sorted(e["entity_id"] for e in vacuums)

    if wanted_vacuum:
        chosen = next((e for e in vacuums if e["entity_id"] == wanted_vacuum), None)
        if chosen is None:
            result.problem = (
                f"Home Assistant nav Ecovacs robota ar ID {wanted_vacuum}. "
                "Pārbaudiet HA_VACUUM_ENTITY."
            )
            return result
    elif vacuums:
        chosen = sorted(vacuums, key=lambda e: e["entity_id"])[0]
    else:
        result.problem = (
            "Home Assistant nav atrasts neviens Ecovacs robots. "
            "Vispirms pievienojiet integrāciju „Ecovacs” Home Assistant iestatījumos."
        )
        return result

    result.vacuum = chosen["entity_id"]
    result.device_id = chosen.get("device_id")
    siblings = [e for e in ecovacs if e.get("device_id") == result.device_id and e is not chosen]
    for role, (domain, key) in ROLES.items():
        for entry in siblings:
            entity_id = str(entry.get("entity_id", ""))
            if not entity_id.startswith(f"{domain}."):
                continue
            unique_id = str(entry.get("unique_id") or "")
            if unique_id.endswith(f"_{key}"):
                if entry.get("disabled_by"):
                    result.disabled[role] = entity_id
                else:
                    result.roles[role] = entity_id
                break
    return result


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _float(value: Any) -> float | None:
    if value in _NO_VALUE:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_rooms(raw: Any) -> tuple[Room, ...]:
    """Parse the vacuum ``rooms`` attribute: ``{name: id}`` or ``{name: [ids]}``."""
    if not isinstance(raw, dict):
        return ()
    rooms: list[Room] = []
    for name, value in raw.items():
        ids = value if isinstance(value, list) else [value]
        for index, room_id in enumerate(ids):
            label = str(name) if len(ids) == 1 else f"{name} ({index + 1})"
            rooms.append(Room(id=str(room_id), name=label))
    return tuple(rooms)


def _minutes(state: dict[str, Any] | None) -> float | None:
    if not state:
        return None
    value = _float(state.get("state"))
    if value is None:
        return None
    unit = (state.get("attributes") or {}).get("unit_of_measurement")
    if unit == "s":
        return round(value / 60, 1)
    if unit == "h":
        return round(value * 60, 1)
    return value


def build_snapshot(
    discovery: Discovery,
    states: dict[str, dict[str, Any]],
    connected: bool,
    device: dict[str, Any] | None = None,
    connection_problem: str | None = None,
) -> RobotSnapshot:
    """Build a snapshot from Home Assistant states. Pure function, easy to test."""
    snap = RobotSnapshot(backend_connected=connected, connection_problem=connection_problem)
    if device:
        snap.robot_name = device.get("name_by_user") or device.get("name")
        snap.model = device.get("model")
    if not connected or not discovery.vacuum:
        snap.connection_problem = connection_problem or discovery.problem
        return snap

    vac = states.get(discovery.vacuum)
    if vac is None:
        snap.connection_problem = "Home Assistant vēl nav atsūtījis robota stāvokli."
        return snap

    def state_of(role: str) -> dict[str, Any] | None:
        entity_id = discovery.roles.get(role)
        return states.get(entity_id) if entity_id else None

    attrs = vac.get("attributes") or {}
    vac_state = vac.get("state")
    snap.robot_available = vac_state not in _UNAVAILABLE
    snap.activity = _ACTIVITY.get(str(vac_state), Activity.UNKNOWN)
    if not snap.robot_available:
        snap.connection_problem = "Home Assistant nevar sazināties ar robotu."

    features = int(attrs.get("supported_features") or 0)
    snap.fan_speed = attrs.get("fan_speed")
    snap.fan_speed_options = tuple(attrs.get("fan_speed_list") or ())
    snap.rooms = parse_rooms(attrs.get("rooms"))

    if (battery := state_of("battery")) is not None:
        value = _float(battery.get("state"))
        snap.battery = int(value) if value is not None else None
    elif isinstance(attrs.get("battery_level"), (int, float)):
        snap.battery = int(attrs["battery_level"])

    if (work_mode := state_of("work_mode")) is not None:
        snap.work_mode = None if work_mode.get("state") in _NO_VALUE else work_mode["state"]
        snap.work_mode_options = tuple((work_mode.get("attributes") or {}).get("options") or ())

    if (active_map := state_of("active_map")) is not None:
        snap.active_map = None if active_map.get("state") in _NO_VALUE else active_map["state"]
        snap.map_options = tuple((active_map.get("attributes") or {}).get("options") or ())

    if (image := state_of("map")) is not None:
        snap.map_updated = _parse_time(image.get("state"))

    if (station := state_of("station_state")) is not None:
        snap.station_state = None if station.get("state") in _NO_VALUE else station["state"]

    snap.last_clean_area = _float((state_of("stats_area") or {}).get("state"))
    snap.last_clean_minutes = _minutes(state_of("stats_time"))

    error_state = state_of("error")
    if error_state is not None and error_state.get("state") not in _NO_VALUE:
        code = _float(error_state.get("state"))
        description = (error_state.get("attributes") or {}).get("description")
        snap.error = translate_error(int(code) if code is not None else None, description)
    if snap.activity == Activity.ERROR and snap.error is None:
        snap.error = GENERIC_ERROR

    for role in SETTING_ROLES:
        if (st := state_of(role)) is None or st.get("state") in _NO_VALUE:
            continue
        domain = discovery.roles[role].split(".", 1)[0]
        a = st.get("attributes") or {}
        if domain == "switch":
            snap.settings[role] = Setting(role, "switch", st["state"] == "on")
        elif domain == "number":
            snap.settings[role] = Setting(
                role, "number", _float(st["state"]), a.get("min"), a.get("max"), a.get("step")
            )

    has_cmd = bool(features & FEATURE_SEND_COMMAND)
    snap.capabilities = {
        "start": bool(features & FEATURE_START),
        "pause": bool(features & FEATURE_PAUSE),
        "stop": bool(features & FEATURE_STOP),
        "return_to_base": bool(features & FEATURE_RETURN_HOME),
        "locate": bool(features & FEATURE_LOCATE),
        "fan_speed": bool(features & FEATURE_FAN_SPEED),
        "clean_rooms": has_cmd and bool(snap.rooms),
        "clean_zone": has_cmd,
        "work_mode": "work_mode" in discovery.roles,
        "active_map": "active_map" in discovery.roles,
        "map": "map" in discovery.roles,
        "error_codes": "error" in discovery.roles,
        "job_finished_event": "last_job" in discovery.roles,
        "empty_dustbin": "empty_dustbin" in discovery.roles,
        "announcements": True,
    }

    times = []
    for entity_id in discovery.entity_ids():
        st = states.get(entity_id)
        if st and st.get("state") not in _UNAVAILABLE:
            t = _parse_time(st.get("last_reported")) or _parse_time(st.get("last_updated"))
            if t:
                times.append(t)
    snap.last_update = max(times) if times else None
    return snap


class HomeAssistantAdapter(RobotAdapter):
    """Controls the robot through Home Assistant."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._conn = HAConnection(
            settings.ha_ws_url,
            settings.ha_token,
            on_event=self._on_event,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
        )
        self._discovery = Discovery()
        self._states: dict[str, dict[str, Any]] = {}
        self._device: dict[str, Any] | None = None
        self._rebuild_lock = asyncio.Lock()

    async def start(self) -> None:
        self._conn.start()

    async def stop(self) -> None:
        await self._conn.stop()
        await self._conn.close_session()

    # --- connection lifecycle -------------------------------------------------
    async def _on_connect(self) -> None:
        await self._conn.call({"type": "subscribe_events", "event_type": "state_changed"})
        await self.rediscover()

    async def rediscover(self) -> None:
        """Re-read the entity registry and all states."""
        registry = await self._conn.call({"type": "config/entity_registry/list"})
        self._discovery = discover(registry or [], self._settings.ha_vacuum_entity)
        self._device = None
        if self._discovery.device_id:
            try:
                devices = await self._conn.call({"type": "config/device_registry/list"})
                self._device = next(
                    (d for d in devices or [] if d.get("id") == self._discovery.device_id), None
                )
            except HAError:
                _LOGGER.warning("Could not read device registry")
        states = await self._conn.call({"type": "get_states"})
        wanted = self._discovery.entity_ids()
        self._states = {s["entity_id"]: s for s in states or [] if s.get("entity_id") in wanted}
        await self._rebuild()

    async def _on_disconnect(self) -> None:
        await self._rebuild()

    async def _on_event(self, event: dict[str, Any]) -> None:
        if event.get("event_type") != "state_changed":
            return
        data = event.get("data") or {}
        entity_id = data.get("entity_id")
        if entity_id not in self._discovery.entity_ids():
            return
        new_state = data.get("new_state")
        old_state = data.get("old_state")
        if new_state is None:
            self._states.pop(entity_id, None)
        else:
            self._states[entity_id] = new_state
        if (
            entity_id == self._discovery.roles.get("last_job")
            and new_state
            and old_state
            and new_state.get("state") != old_state.get("state")
            and new_state.get("state") not in _NO_VALUE
        ):
            event_type = (new_state.get("attributes") or {}).get("event_type")
            await self._emit("job_finished", {"result": event_type})
        await self._rebuild()

    async def _rebuild(self) -> None:
        async with self._rebuild_lock:
            problem = None
            if not self._conn.connected:
                problem = self._conn.last_error or "Nav savienojuma ar Home Assistant."
            snapshot = build_snapshot(
                self._discovery, self._states, self._conn.connected, self._device, problem
            )
            await self._publish(snapshot)

    # --- commands -------------------------------------------------------------
    async def _service(
        self, domain: str, service: str, data: dict[str, Any], timeout: float | None = None
    ) -> None:
        if not self._conn.connected:
            raise NotConnectedError("Nav savienojuma ar Home Assistant.")
        try:
            await self._conn.call(
                {
                    "type": "call_service",
                    "domain": domain,
                    "service": service,
                    "service_data": data,
                },
                timeout=timeout or self._settings.command_timeout,
            )
        except HAError as err:
            raise AdapterError(
                "Home Assistant atteicās izpildīt komandu.", f"{err.code}: {err.message}"
            ) from err
        except TimeoutError as err:
            raise AdapterError("Komanda netika apstiprināta laikā.", "timeout") from err
        except ConnectionError as err:
            raise NotConnectedError("Savienojums ar Home Assistant pārtrūka.") from err

    def _role(self, role: str) -> str:
        entity_id = self._discovery.roles.get(role)
        if not entity_id:
            raise UnsupportedError("Šī funkcija jūsu robotam nav pieejama.")
        return entity_id

    async def send(self, request: CommandRequest) -> None:
        vacuum = self._discovery.vacuum
        if not vacuum:
            raise NotConnectedError("Robots nav atrasts Home Assistant.")
        name, params = request.name, request.params
        target = {"entity_id": vacuum}
        match name:
            case CommandName.START | CommandName.RESUME:
                await self._service("vacuum", "start", target)
            case CommandName.PAUSE:
                await self._service("vacuum", "pause", target)
            case CommandName.STOP:
                await self._service("vacuum", "stop", target)
            case CommandName.RETURN_TO_BASE:
                await self._service("vacuum", "return_to_base", target)
            case CommandName.LOCATE:
                await self._service("vacuum", "locate", target)
            case CommandName.CLEAN_ROOMS:
                await self._service(
                    "vacuum",
                    "send_command",
                    {
                        **target,
                        "command": "spot_area",
                        "params": {
                            "rooms": ",".join(params["rooms"]),
                            "cleanings": params.get("cleanings", 1),
                        },
                    },
                )
            case CommandName.CLEAN_ZONE:
                await self._service(
                    "vacuum",
                    "send_command",
                    {
                        **target,
                        "command": "custom_area",
                        "params": {
                            "coordinates": ",".join(str(int(c)) for c in params["coordinates"]),
                            "cleanings": params.get("cleanings", 1),
                        },
                    },
                )
            case CommandName.SET_FAN_SPEED:
                await self._service("vacuum", "set_fan_speed", {**target, "fan_speed": params["value"]})
            case CommandName.SET_WORK_MODE:
                await self._service(
                    "select", "select_option",
                    {"entity_id": self._role("work_mode"), "option": params["value"]},
                )
            case CommandName.SET_ACTIVE_MAP:
                await self._service(
                    "select", "select_option",
                    {"entity_id": self._role("active_map"), "option": params["value"]},
                )
            case CommandName.SET_SETTING:
                entity_id = self._role(params["key"])
                if entity_id.startswith("switch."):
                    service = "turn_on" if params["value"] else "turn_off"
                    await self._service("switch", service, {"entity_id": entity_id})
                else:
                    await self._service(
                        "number", "set_value", {"entity_id": entity_id, "value": params["value"]}
                    )
            case CommandName.EMPTY_DUSTBIN:
                await self._service("button", "press", {"entity_id": self._role("empty_dustbin")})
            case CommandName.REFRESH_MAP:
                await self._service(
                    "homeassistant", "update_entity", {"entity_id": self._role("map")}
                )
            case _:
                raise UnsupportedError("Nezināma komanda.")

    # --- map --------------------------------------------------------------------
    async def get_map_svg(self) -> bytes | None:
        entity_id = self._discovery.roles.get("map")
        if not entity_id:
            return None
        url = f"{self._settings.ha_url}/api/image_proxy/{entity_id}"
        try:
            async with self._conn.http_session.get(
                url,
                headers={"Authorization": f"Bearer {self._settings.ha_token}"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status in (404, 500):
                    return None
                if resp.status != 200:
                    raise AdapterError("Neizdevās ielādēt karti.", f"HTTP {resp.status}")
                return await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise AdapterError("Neizdevās ielādēt karti.", type(err).__name__) from err

    # --- announcements ------------------------------------------------------------
    async def speech_targets(self) -> SpeechTargets:
        if not self._conn.connected:
            raise NotConnectedError("Nav savienojuma ar Home Assistant.")
        states = await self._conn.call({"type": "get_states"})
        services = await self._conn.call({"type": "get_services"})
        ids = sorted(s["entity_id"] for s in states or [])
        return SpeechTargets(
            tts_entities=tuple(i for i in ids if i.startswith("tts.")),
            media_players=tuple(i for i in ids if i.startswith("media_player.")),
            notify_services=tuple(
                sorted(f"notify.{name}" for name in (services or {}).get("notify", {}))
            ),
        )

    async def speak(
        self,
        tts_entity: str,
        media_player: str,
        message: str,
        language: str | None,
        volume: float | None,
    ) -> None:
        if volume is not None:
            await self._service(
                "media_player", "volume_set",
                {"entity_id": media_player, "volume_level": volume},
            )
        data: dict[str, Any] = {
            "entity_id": tts_entity,
            "media_player_entity_id": media_player,
            "message": message,
        }
        if language:
            data["language"] = language
        await self._service("tts", "speak", data)

    async def notify(self, service: str, message: str) -> None:
        domain, _, name = service.partition(".")
        if domain != "notify" or not name:
            raise AdapterError("Nederīgs paziņojumu serviss.")
        await self._service("notify", name, {"title": "Robots", "message": message})

    # --- diagnostics --------------------------------------------------------------
    async def diagnostics(self) -> dict[str, Any]:
        vac = self._states.get(self._discovery.vacuum or "") or {}
        attrs = vac.get("attributes") or {}
        return {
            "integration": "homeassistant",
            "ha_connected": self._conn.connected,
            "ha_version": self._conn.ha_version,
            "ha_auth_failed": self._conn.auth_failed,
            "ha_last_error": self._conn.last_error,
            "ha_url": self._settings.ha_url,
            "vacuum_entity": self._discovery.vacuum,
            "vacuum_candidates": self._discovery.candidates,
            "discovery_problem": self._discovery.problem,
            "entities": dict(sorted(self._discovery.roles.items())),
            "disabled_in_ha": dict(sorted(self._discovery.disabled.items())),
            "recommended_to_enable": [
                self._discovery.disabled[r] for r in RECOMMENDED_ENABLED if r in self._discovery.disabled
            ],
            "device": {
                "model": (self._device or {}).get("model"),
                "manufacturer": (self._device or {}).get("manufacturer"),
                "sw_version": (self._device or {}).get("sw_version"),
            },
            "vacuum_state": vac.get("state"),
            "vacuum_supported_features": attrs.get("supported_features"),
            "room_count": len(parse_rooms(attrs.get("rooms"))),
        }
