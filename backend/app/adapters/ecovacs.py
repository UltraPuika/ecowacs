"""Robot adapter that talks directly to the Ecovacs cloud. No Home Assistant needed.

It uses ``deebot-client``, the same library Home Assistant's Ecovacs integration
uses: REST login with the Ecovacs account, then MQTT for live robot updates.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp
from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.capabilities import Capabilities, CapabilityNumber, CapabilitySet
from deebot_client.commands import StationAction
from deebot_client.device import Device
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
    CachedMapInfoEvent,
    CleanCountEvent,
    CleanJobStatus,
    EnableEvent,
    ErrorEvent,
    Event,
    FanSpeedEvent,
    FanSpeedLevel,
    MapChangedEvent,
    ReportStatsEvent,
    RoomsEvent,
    StateEvent,
    StationEvent,
    StatsEvent,
    VolumeEvent,
    WorkMode,
    WorkModeEvent,
)
from deebot_client.events.water_info import WaterAmount, WaterAmountEvent, WaterCustomAmountEvent
from deebot_client.exceptions import (
    DeebotError,
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
    InvalidVerificationCodeError,
    MapError,
)
from deebot_client.models import AccountCredentials, CleanAction, CleanMode, DeviceInfo, State
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5

from ..config import Settings
from ..errors_lv import GENERIC_ERROR, translate_error
from ..models import Activity, CommandName, CommandRequest, RobotSnapshot, Room, Setting
from .base import AdapterError, NotConnectedError, RobotAdapter, UnsupportedError

_LOGGER = logging.getLogger(__name__)

STATE_FILE = "ecovacs.json"
RETRY_MIN = 30.0
RETRY_MAX = 600.0
RETRY_BAD_LOGIN = 3600.0

_ACTIVITY = {
    State.IDLE: Activity.IDLE,
    State.CLEANING: Activity.CLEANING,
    State.RETURNING: Activity.RETURNING,
    State.DOCKED: Activity.DOCKED,
    State.ERROR: Activity.ERROR,
    State.PAUSED: Activity.PAUSED,
}
_JOB_DONE = (
    CleanJobStatus.FINISHED,
    CleanJobStatus.FINISHED_WITH_WARNINGS,
    CleanJobStatus.MANUALLY_STOPPED,
)

MSG_BAD_LOGIN = "Ecovacs noraidīja e-pastu vai paroli. Pārbaudiet ECOVACS_USERNAME un ECOVACS_PASSWORD."
MSG_VERIFY = (
    "Ecovacs prasa apstiprināt šo ierīci ar kodu no e-pasta. "
    "Atveriet Iestatījumi → Ecovacs konta apstiprināšana."
)
MSG_NO_CLOUD = "Nav savienojuma ar Ecovacs mākoni."


class _NoRobotError(DeebotError):
    """No usable robot in the account. The message is Latvian."""


def _key(member: Any) -> str:
    """Same option names as Home Assistant: the enum member name in lower case."""
    return str(member.name).lower()


def _setting_capabilities(caps: Capabilities) -> dict[str, Any]:
    return {
        "carpet_auto_fan_boost": caps.settings.carpet_auto_fan_boost,
        "continuous_cleaning": caps.clean.continuous,
        "child_lock": caps.settings.child_lock,
        "water_amount": caps.water.amount if caps.water else None,
        "clean_count": caps.clean.count,
        "volume": caps.settings.volume,
    }


def _setting(key: str, cap: Any, event: Event | None) -> Setting | None:
    match event:
        case None:
            return None
        case EnableEvent(enabled=enabled):
            return Setting(key, "switch", enabled)
        case WaterCustomAmountEvent(value=value) if isinstance(cap, CapabilityNumber):
            return Setting(key, "number", value, cap.min, cap.max, 1)
        case WaterAmountEvent(value=value):
            return Setting(key, "select", _key(value), options=tuple(_key(t) for t in cap.types))
        case CleanCountEvent(count=count):
            return Setting(key, "number", count, 1, 4, 1)
        case VolumeEvent(volume=volume, maximum=maximum):
            return Setting(key, "number", volume, 0, maximum or 10, 1)
    return None


def parse_outline(coordinates: str) -> tuple[tuple[int, int], ...]:
    """Parse a room polygon "x,y;x,y;..." (older robots). Newer robots send nothing."""
    points: list[tuple[int, int]] = []
    for pair in coordinates.split(";"):
        parts = pair.strip().split(",")
        if len(parts) != 2:
            return ()
        try:
            points.append((round(float(parts[0])), round(float(parts[1]))))
        except ValueError:
            return ()
    return tuple(points) if len(points) >= 3 else ()


def map_names(event: CachedMapInfoEvent | None) -> tuple[dict[str, str], str | None]:
    """Return ({name: map_id}, active name) like Home Assistant's active-map select."""
    if event is None:
        return {}, None
    by_name: dict[str, str] = {}
    active = None
    for info in event.maps:
        name = info.name or info.id
        by_name[name] = info.id
        if info.using:
            active = name
    return by_name, active


def build_snapshot(
    caps: Capabilities,
    last: Callable[[type[Any]], Any],
    *,
    connected: bool,
    problem: str | None = None,
    robot_name: str | None = None,
    model: str | None = None,
    map_updated: datetime | None = None,
    last_update: datetime | None = None,
) -> RobotSnapshot:
    """Build a snapshot from the last event of each type. Pure function, easy to test."""
    snap = RobotSnapshot(
        backend_connected=connected,
        connection_problem=problem,
        robot_name=robot_name,
        model=model,
        map_updated=map_updated,
        last_update=last_update,
    )
    if not connected:
        snap.connection_problem = problem or MSG_NO_CLOUD
        return snap

    availability: AvailabilityEvent | None = last(AvailabilityEvent)
    snap.robot_available = bool(availability and availability.available)
    if not snap.robot_available:
        snap.connection_problem = problem or (
            "Robots nav sasniedzams. Pārbaudiet, vai tas ir ieslēgts un savienots ar Wi-Fi."
            if availability
            else "Gaida atbildi no robota…"
        )

    if state := last(StateEvent):
        snap.activity = _ACTIVITY.get(state.state, Activity.UNKNOWN)
    if battery := last(BatteryEvent):
        snap.battery = int(battery.value)

    if caps.fan_speed:
        snap.fan_speed_options = tuple(_key(t) for t in caps.fan_speed.types)
        if fan := last(FanSpeedEvent):
            snap.fan_speed = _key(fan.speed)
    if caps.clean.work_mode:
        snap.work_mode_options = tuple(_key(t) for t in caps.clean.work_mode.types)
        if mode := last(WorkModeEvent):
            snap.work_mode = _key(mode.mode)

    can_switch_map = False
    if caps.map:
        if rooms := last(RoomsEvent):
            snap.rooms = tuple(
                Room(str(r.id), r.name or f"Telpa {r.id}", parse_outline(r.coordinates or ""))
                for r in sorted(rooms.rooms, key=lambda r: r.id)
            )
        by_name, snap.active_map = map_names(last(CachedMapInfoEvent))
        snap.map_options = tuple(sorted(by_name, key=lambda n: (n.isdigit(), n.lower())))
        can_switch_map = isinstance(caps.map.major, CapabilitySet) and bool(snap.map_options)

    if caps.station and (station := last(StationEvent)):
        snap.station_state = _key(station.state)

    if stats := last(StatsEvent):
        snap.last_clean_area = float(stats.area) if stats.area is not None else None
        snap.last_clean_minutes = round(stats.time / 60, 1) if stats.time is not None else None

    if error := last(ErrorEvent):
        snap.error = translate_error(error.code, error.description)
    if snap.activity == Activity.ERROR and snap.error is None:
        snap.error = GENERIC_ERROR

    for key, cap in _setting_capabilities(caps).items():
        if cap is not None and (setting := _setting(key, cap, last(cap.event))):
            snap.settings[key] = setting

    area = caps.clean.action.area is not None
    snap.capabilities = {
        "start": True,
        "pause": True,
        "stop": True,
        "return_to_base": True,
        "locate": True,
        "fan_speed": caps.fan_speed is not None,
        "clean_rooms": area and bool(snap.rooms),
        "clean_zone": area,
        "work_mode": caps.clean.work_mode is not None,
        "active_map": can_switch_map,
        "map": caps.map is not None,
        "error_codes": True,
        "job_finished_event": True,
        "empty_dustbin": bool(caps.station and StationAction.EMPTY_DUSTBIN in caps.station.action.types),
        "announcements": False,
    }
    return snap


def choose_device(devices: list[DeviceInfo], wanted: str) -> DeviceInfo | None:
    """Pick the robot named by ECOVACS_DEVICE (id, nickname or model), else the first."""
    if not wanted:
        return devices[0] if devices else None
    wanted_l = wanted.strip().lower()
    for info in devices:
        api = info.api
        names = (api.get("did"), api.get("nick"), api.get("name"), api.get("deviceName"))
        if any(isinstance(n, str) and n.lower() == wanted_l for n in names):
            return info
    return None


class _Store:
    """Keeps a stable client device ID and the account token between restarts."""

    def __init__(self, path: Path, username: str) -> None:
        self._path = path
        self._user_hash = md5(username.strip().lower())
        self.data: dict[str, Any] = {}
        try:
            self.data = json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            self.data = {}
        if not isinstance(self.data, dict):
            self.data = {}
        if self.data.get("user") != self._user_hash:
            # another account: never reuse its token
            self.data = {"device_id": self.data.get("device_id")}
        if not isinstance(self.data.get("device_id"), str):
            self.data["device_id"] = secrets.token_hex(16)
        self.data["user"] = self._user_hash
        self._write()

    @property
    def device_id(self) -> str:
        return str(self.data["device_id"])

    @property
    def account(self) -> AccountCredentials | None:
        acc = self.data.get("account")
        if isinstance(acc, dict) and acc.get("access_token") and acc.get("user_id"):
            return AccountCredentials(str(acc["access_token"]), str(acc["user_id"]))
        return None

    def save_account(self, account: AccountCredentials) -> None:
        self.data["account"] = {"access_token": account.access_token, "user_id": account.user_id}
        self._write()

    def _write(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle)
            os.replace(tmp, self._path)
        except OSError:
            _LOGGER.warning("Could not save Ecovacs session file %s", self._path)


class EcovacsAdapter(RobotAdapter):
    """Controls the robot through the Ecovacs cloud."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._store = _Store(settings.data_dir / STATE_FILE, settings.ecovacs_username)
        self._session: aiohttp.ClientSession | None = None
        self._authenticator: Authenticator | None = None
        self._mqtt: MqttClient | None = None
        self._device: Device | None = None
        self._unsubscribers: list[Callable[[], None]] = []
        self._task: asyncio.Task[None] | None = None
        self._wake = asyncio.Event()
        self._rebuild_lock = asyncio.Lock()
        self._problem: str | None = None
        self._map_updated: datetime | None = None
        self._last_update: datetime | None = None
        self._found: list[dict[str, Any]] = []
        self.verification_required = False

    # --- lifecycle ----------------------------------------------------------------
    async def start(self) -> None:
        self._session = aiohttp.ClientSession()
        rest = create_rest_config(
            self._session,
            device_id=self._store.device_id,
            alpha_2_country=self._settings.ecovacs_country,
        )
        self._authenticator = Authenticator(
            rest,
            self._settings.ecovacs_username,
            md5(self._settings.ecovacs_password),
            account_credentials=self._store.account,
        )

        async def on_account(account: AccountCredentials) -> None:
            self._store.save_account(account)

        self._authenticator.subscribe_account_credentials(on_account)
        self._mqtt = MqttClient(
            create_mqtt_config(device_id=self._store.device_id, country=rest.country),
            self._authenticator,
        )
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._teardown_device()
        if self._mqtt:
            await self._mqtt.disconnect()
        if self._authenticator:
            await self._authenticator.teardown()
        if self._session:
            await self._session.close()

    async def _run(self) -> None:
        delay = RETRY_MIN
        while True:
            self._wake.clear()
            try:
                await self._connect()
                return
            except InvalidAuthenticationError:
                _LOGGER.error("Ecovacs rejected the username or password")
                self._problem, wait = MSG_BAD_LOGIN, RETRY_BAD_LOGIN
            except DeviceVerificationRequiredError:
                _LOGGER.warning("Ecovacs requires e-mail verification of this client")
                self.verification_required = True
                self._problem, wait = MSG_VERIFY, None
            except _NoRobotError as err:
                self._problem, wait = str(err), RETRY_MAX
            except (DeebotError, aiohttp.ClientError, TimeoutError, OSError) as err:
                _LOGGER.warning("Ecovacs connection failed: %s", type(err).__name__)
                self._problem, wait = f"{MSG_NO_CLOUD} ({type(err).__name__})", delay
                delay = min(delay * 2, RETRY_MAX)
            await self._teardown_device()
            await self._rebuild()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), wait)

    async def _connect(self) -> None:
        if self._authenticator is None or self._mqtt is None:
            raise RuntimeError("start() was not called")
        self._problem = None
        await self._rebuild()
        devices = await ApiClient(self._authenticator).get_devices()
        self.verification_required = False
        self._found = [
            {"model": d.api.get("deviceName"), "class": d.api.get("class"), "nick": d.api.get("nick"),
             "supported": True}
            for d in devices.mqtt
        ] + [
            {"model": d.get("deviceName"), "class": d.get("class"), "nick": d.get("nick"), "supported": False}
            for d in [*devices.xmpp, *devices.not_supported]
        ]
        info = choose_device(devices.mqtt, self._settings.ecovacs_device)
        if info is None:
            if self._settings.ecovacs_device:
                raise _NoRobotError(f"Ecovacs kontā nav robota „{self._settings.ecovacs_device}”. Pārbaudiet ECOVACS_DEVICE.")
            if devices.xmpp or devices.not_supported:
                raise _NoRobotError("Jūsu Ecovacs robota modelis šai lietotnei (deebot-client) nav atbalstīts.")
            raise _NoRobotError("Ecovacs kontā nav atrasts neviens robots.")

        device = Device(info, self._authenticator)
        await device.initialize(self._mqtt)
        self._device = device
        self._subscribe(device)
        _LOGGER.info("Connected to Ecovacs robot %s", info.api.get("deviceName") or info.api.get("class"))
        await self._rebuild()

    def _subscribe(self, device: Device) -> None:
        caps = device.capabilities
        bus = device.events

        async def on_any(_event: Event) -> None:
            self._last_update = datetime.now(UTC)
            await self._rebuild()

        async def on_report(event: ReportStatsEvent) -> None:
            await on_any(event)
            if event.status in _JOB_DONE:
                await self._emit("job_finished", {"result": _key(event.status)})

        async def on_map(event: MapChangedEvent) -> None:
            self._map_updated = event.when
            await self._rebuild()

        types: list[type[Event]] = [
            AvailabilityEvent, StateEvent, BatteryEvent, ErrorEvent, StatsEvent,
        ]
        if caps.fan_speed:
            types.append(FanSpeedEvent)
        if caps.clean.work_mode:
            types.append(WorkModeEvent)
        if caps.station:
            types.append(StationEvent)
        if caps.map:
            types += [RoomsEvent, CachedMapInfoEvent]
            self._unsubscribers.append(bus.subscribe(MapChangedEvent, on_map))
        types += [cap.event for cap in _setting_capabilities(caps).values() if cap is not None]
        for event_type in types:
            self._unsubscribers.append(bus.subscribe(event_type, on_any))
        self._unsubscribers.append(bus.subscribe(ReportStatsEvent, on_report))

    async def _teardown_device(self) -> None:
        for unsubscribe in self._unsubscribers:
            with contextlib.suppress(ValueError):
                unsubscribe()
        self._unsubscribers.clear()
        if self._device:
            device, self._device = self._device, None
            try:
                await device.teardown()
            except Exception:
                _LOGGER.exception("Ecovacs device teardown failed")

    async def rediscover(self) -> None:
        """Reconnect and re-read the robot list."""
        if self._task and not self._task.done():
            self._wake.set()
            return
        await self._teardown_device()
        self._task = asyncio.create_task(self._run())

    async def _rebuild(self) -> None:
        async with self._rebuild_lock:
            device = self._device
            if device is None:
                snap = RobotSnapshot(connection_problem=self._problem or "Savienojas ar Ecovacs…")
            else:
                api = device.device_info
                snap = build_snapshot(
                    device.capabilities,
                    device.events.get_last_event,
                    connected=True,
                    robot_name=api.get("nick") or api.get("deviceName"),
                    model=api.get("deviceName") or api.get("class"),
                    map_updated=self._map_updated,
                    last_update=self._last_update,
                )
            await self._publish(snap)

    # --- e-mail verification --------------------------------------------------------
    async def request_verification_code(self) -> None:
        """Ask Ecovacs to e-mail a one-time code for this client."""
        if not self._authenticator:
            raise NotConnectedError(MSG_NO_CLOUD)
        try:
            await self._authenticator.request_device_verification_code()
        except (DeebotError, aiohttp.ClientError, TimeoutError) as err:
            raise AdapterError("Neizdevās nosūtīt kodu. Pamēģiniet vēlreiz pēc brīža.", type(err).__name__) from err

    async def verify(self, code: str) -> None:
        """Confirm this client with the e-mailed code, then connect."""
        if not self._authenticator:
            raise NotConnectedError(MSG_NO_CLOUD)
        try:
            await self._authenticator.verify_device(code)
        except InvalidVerificationCodeError as err:
            raise AdapterError("Nepareizs vai novecojis kods.") from err
        except (DeebotError, aiohttp.ClientError, TimeoutError) as err:
            raise AdapterError("Neizdevās apstiprināt kodu.", type(err).__name__) from err
        self.verification_required = False
        await self.rediscover()

    # --- commands -------------------------------------------------------------
    async def _execute(self, command: Any) -> None:
        device = self._device
        if device is None:
            raise NotConnectedError(self._problem or MSG_NO_CLOUD)
        try:
            await asyncio.wait_for(device.execute_command(command), self._settings.command_timeout)
        except TimeoutError as err:
            raise AdapterError("Komanda netika apstiprināta laikā.", "timeout") from err
        except (DeebotError, aiohttp.ClientError) as err:
            raise AdapterError("Ecovacs mākonis atteicās izpildīt komandu.", type(err).__name__) from err

    async def send(self, request: CommandRequest) -> None:
        device = self._device
        if device is None:
            raise NotConnectedError(self._problem or MSG_NO_CLOUD)
        caps = device.capabilities
        name, params = request.name, request.params
        action = caps.clean.action
        match name:
            case CommandName.START:
                await self._execute(action.command(CleanAction.START))
            case CommandName.RESUME:
                await self._execute(action.command(CleanAction.RESUME))
            case CommandName.PAUSE:
                await self._execute(action.command(CleanAction.PAUSE))
            case CommandName.STOP:
                await self._execute(action.command(CleanAction.STOP))
            case CommandName.RETURN_TO_BASE:
                await self._execute(caps.charge.execute())
            case CommandName.LOCATE:
                await self._execute(caps.play_sound.execute())
            case CommandName.CLEAN_ROOMS:
                if action.area is None:
                    raise UnsupportedError("Telpu tīrīšana šim robotam nav pieejama.")
                rooms: list[int | float] = [int(r) for r in params["rooms"]]
                await self._execute(action.area(CleanMode.SPOT_AREA, rooms, params.get("cleanings", 1)))
            case CommandName.CLEAN_ZONE:
                if action.area is None:
                    raise UnsupportedError("Zonas tīrīšana šim robotam nav pieejama.")
                coords: list[int | float] = [int(c) for c in params["coordinates"]]
                await self._execute(action.area(CleanMode.CUSTOM_AREA, coords, params.get("cleanings", 1)))
            case CommandName.SET_FAN_SPEED:
                if not caps.fan_speed:
                    raise UnsupportedError("Sūkšanas jauda šim robotam nav maināma.")
                await self._execute(caps.fan_speed.set(FanSpeedLevel[params["value"].upper()]))
            case CommandName.SET_WORK_MODE:
                if not caps.clean.work_mode:
                    raise UnsupportedError("Tīrīšanas veids šim robotam nav maināms.")
                await self._execute(caps.clean.work_mode.set(WorkMode[params["value"].upper()]))
            case CommandName.SET_ACTIVE_MAP:
                major = caps.map.major if caps.map else None
                by_name, _ = map_names(device.events.get_last_event(CachedMapInfoEvent))
                if not isinstance(major, CapabilitySet) or params["value"] not in by_name:
                    raise UnsupportedError("Karti nevar nomainīt.")
                await self._execute(major.set(by_name[params["value"]]))
                device.events.request_refresh(CachedMapInfoEvent)
            case CommandName.SET_SETTING:
                await self._execute(self._setting_command(caps, params["key"], params["value"]))
            case CommandName.EMPTY_DUSTBIN:
                if not (caps.station and StationAction.EMPTY_DUSTBIN in caps.station.action.types):
                    raise UnsupportedError("Šai stacijai nav putekļu iztukšošanas.")
                await self._execute(caps.station.action.execute(StationAction.EMPTY_DUSTBIN))
            case CommandName.REFRESH_MAP:
                if device.map is None:
                    raise UnsupportedError("Karte šim robotam nav pieejama.")
                try:
                    device.map.refresh()
                except MapError as err:
                    raise AdapterError("Karte vēl nav ielādēta.") from err
            case _:
                raise UnsupportedError("Nezināma komanda.")

    @staticmethod
    def _setting_command(caps: Capabilities, key: str, value: Any) -> Any:
        cap = _setting_capabilities(caps).get(key)
        if cap is None:
            raise UnsupportedError("Šī funkcija jūsu robotam nav pieejama.")
        if isinstance(value, bool):
            return cap.set(value)
        if isinstance(value, str):
            return cap.set(WaterAmount[value.upper()])
        return cap.set(int(value))

    # --- map --------------------------------------------------------------------
    async def get_map_svg(self) -> bytes | None:
        device = self._device
        if device is None or device.map is None:
            return None
        try:
            svg = device.map.get_svg_map()
        except MapError:
            return None
        except Exception as err:
            raise AdapterError("Neizdevās ielādēt karti.", type(err).__name__) from err
        return svg.encode() if svg else None

    def map_rotation(self) -> int | None:
        device = self._device
        if device is None or device.map is None:
            return None
        info: CachedMapInfoEvent | None = device.events.get_last_event(CachedMapInfoEvent)
        used = next((m for m in info.maps if m.using), None) if info else None
        if used is None:
            return 0
        try:
            return int(str(used.angle.name).removeprefix("DEG_"))
        except ValueError:
            return None

    # --- diagnostics --------------------------------------------------------------
    async def diagnostics(self) -> dict[str, Any]:
        device = self._device
        api = device.device_info if device else {}
        mqtt_last = self._mqtt.last_message_received_at if self._mqtt else None
        return {
            "integration": "ecovacs",
            "country": self._settings.ecovacs_country,
            "cloud_connected": device is not None,
            "verification_required": self.verification_required,
            "problem": self._problem,
            "robots_in_account": self._found,
            "device": {
                "model": api.get("deviceName"),
                "class": api.get("class"),
                "firmware": device.fw_version if device else None,
            },
            "mqtt_last_message": mqtt_last.isoformat() if mqtt_last else None,
            "map_supported": bool(device and device.map),
        }

