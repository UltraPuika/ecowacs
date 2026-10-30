"""Robot adapter that talks to the Ecovacs cloud directly through deebot-client.

This is the same library Home Assistant's Ecovacs integration uses, so the
robot support is identical (the X9 PRO OMNI has its own profile, ``ilt3k8``).
What is different: there is no Home Assistant, so there is no text-to-speech or
phone-notification route, and the login is done once with
``python -m app.ecovacs_login``. The password is never kept; the app renews
its session from the saved Ecovacs token.

Nothing here has been tested against a real robot or the real Ecovacs cloud.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Protocol

import aiohttp
from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.capabilities import CapabilitySet
from deebot_client.commands import StationAction
from deebot_client.device import Device
from deebot_client.events import (
    AvailabilityEvent,
    BatteryEvent,
    CarpetAutoFanBoostEvent,
    ChildLockEvent,
    CleanCountEvent,
    CleanJobStatus,
    ContinuousCleaningEvent,
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
from deebot_client.events.map import CachedMapInfoEvent, MajorMapEvent, MapChangedEvent
from deebot_client.events.station import StationEvent
from deebot_client.events.water_info import WaterCustomAmountEvent
from deebot_client.exceptions import AuthenticationError, DeebotError, MapError
from deebot_client.models import AccountCredentials, CleanAction, CleanMode, DeviceInfo, State
from deebot_client.mqtt_client import MqttClient, create_mqtt_config

from ..config import Settings
from ..ecovacs_session import StoredSession, load_session
from ..errors_lv import GENERIC_ERROR, translate_error
from ..models import Activity, CommandName, CommandRequest, RobotSnapshot, Room, Setting
from .base import AdapterError, NotConnectedError, RobotAdapter, UnsupportedError

_LOGGER = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 120.0
MIN_RETRY = 5.0
MAX_RETRY = 120.0

LOGIN_HINT = (
    "Palaidiet vienreizējo pieslēgšanos: docker compose run --rm backend python -m app.ecovacs_login "
    "(skatiet docs/DIRECT_MODE.md)."
)

_ACTIVITY = {
    State.IDLE: Activity.IDLE,
    State.CLEANING: Activity.CLEANING,
    State.RETURNING: Activity.RETURNING,
    State.DOCKED: Activity.DOCKED,
    State.ERROR: Activity.ERROR,
    State.PAUSED: Activity.PAUSED,
}
_UNNAMED_MAP = "Karte {id}"


class DirectProblem(Exception):
    """A condition that retrying cannot fix. The message is shown to the user (Latvian)."""


@dataclass
class Link:
    """A live connection: the robot plus what is needed to close it."""

    device: Device
    close: Callable[[], Awaitable[None]]
    candidates: list[dict[str, Any]] = field(default_factory=list)


class Connector(Protocol):
    """Opens a Link. Replaceable in tests."""

    async def connect(self, stored: StoredSession, wanted: str) -> Link: ...


def _label(info: dict[str, Any]) -> str:
    return str(info.get("nick") or info.get("name") or info.get("did") or "?")


def choose_device(
    mqtt: list[DeviceInfo],
    legacy: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
    wanted: str,
) -> DeviceInfo:
    """Pick the robot to control, or explain (in Latvian) why none can be used."""
    if not mqtt:
        if legacy:
            raise DirectProblem(
                "Šis robots izmanto vecāku Ecovacs protokolu, ko lietotne neatbalsta. "
                "Izmantojiet Ecovacs Home lietotni."
            )
        if unsupported:
            raise DirectProblem(
                "Ecovacs bibliotēka vēl neatbalsta šo robota modeli. Skatiet diagnostiku un docs/DIRECT_MODE.md."
            )
        raise DirectProblem("Šajā Ecovacs kontā nav neviena robota.")
    if wanted:
        key = wanted.lower()
        for info in mqtt:
            api = info.api
            if key in (str(api.get("did", "")).lower(), str(api.get("nick", "")).lower(),
                       str(api.get("name", "")).lower()):
                return info
        raise DirectProblem(f"Kontā nav robota „{wanted}”. Pārbaudiet ECOVACS_DEVICE.")
    return sorted(mqtt, key=lambda i: _label(i.api))[0]


class EcovacsConnector:
    """Production connector: REST login with the saved token, then MQTT."""

    async def connect(self, stored: StoredSession, wanted: str) -> Link:
        http = aiohttp.ClientSession()
        authenticator: Authenticator | None = None
        mqtt: MqttClient | None = None
        device: Device | None = None

        async def close() -> None:
            if device is not None:
                with contextlib.suppress(Exception):
                    await device.teardown()
            if mqtt is not None:
                with contextlib.suppress(Exception):
                    await mqtt.disconnect()
            if authenticator is not None:
                with contextlib.suppress(Exception):
                    await authenticator.teardown()
            await http.close()

        try:
            # The e-mail and password are not needed: the saved token renews the session.
            authenticator = Authenticator(
                create_rest_config(http, device_id=stored.device_id, alpha_2_country=stored.country),
                "",
                "",
                account_credentials=AccountCredentials(
                    access_token=stored.access_token, user_id=stored.user_id
                ),
            )
            devices = await ApiClient(authenticator).get_devices()
            await authenticator.authenticate()
            info = choose_device(devices.mqtt, devices.xmpp, devices.not_supported, wanted)

            config = await asyncio.to_thread(
                partial(create_mqtt_config, device_id=stored.device_id, country=stored.country)
            )
            mqtt = MqttClient(config, authenticator)
            await mqtt.verify_config()
            device = Device(info, authenticator)
            await device.initialize(mqtt)
        except BaseException:
            await close()
            raise
        candidates = [
            {"name": _label(i.api), "model": i.api.get("deviceName"), "class": i.api.get("class")}
            for i in devices.mqtt
        ]
        return Link(device, close, candidates)


def numbered_rooms(rooms: list[Any]) -> tuple[Room, ...]:
    """Library rooms to app rooms. Duplicate names get a number so they can be told apart."""
    counts: dict[str, int] = {}
    for room in rooms:
        counts[str(room.name)] = counts.get(str(room.name), 0) + 1
    seen: dict[str, int] = {}
    out: list[Room] = []
    for room in sorted(rooms, key=lambda r: int(r.id)):
        name = str(room.name) or f"Telpa {room.id}"
        if counts[str(room.name)] > 1:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name} ({seen[name]})"
        out.append(Room(id=str(room.id), name=name))
    return tuple(out)


class DirectAdapter(RobotAdapter):
    """Controls the robot through the Ecovacs cloud with deebot-client."""

    def __init__(self, settings: Settings, connector: Connector | None = None) -> None:
        super().__init__()
        self._settings = settings
        self._connector: Connector = connector or EcovacsConnector()
        self._task: asyncio.Task[None] | None = None
        self._link: Link | None = None
        self._unsubscribe: list[Callable[[], None]] = []
        self._rebuild_lock = asyncio.Lock()

        self._connected = False
        self._problem: str | None = None
        self._fatal = False
        self._last_error_text: str | None = None
        self._available: bool | None = None
        self._last_seen: datetime | None = None

        self._activity = Activity.UNKNOWN
        self._battery: int | None = None
        self._fan_speed: str | None = None
        self._work_mode: str | None = None
        self._rooms: tuple[Room, ...] = ()
        self._maps: dict[str, str] = {}  # label -> map id
        self._active_map_id: str | None = None
        self._map_updated: datetime | None = None
        self._error: Any = None
        self._station: str | None = None
        self._area: float | None = None
        self._minutes: float | None = None
        self._values: dict[str, Any] = {}  # switches and numbers
        self._limits: dict[str, tuple[float, float, float]] = {}
        self._robot_name: str | None = None
        self._model: str | None = None

    # --- lifecycle -------------------------------------------------------------
    async def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="direct-connection")

    async def stop(self) -> None:
        await self._cancel_task()
        await self._close_link()

    async def rediscover(self) -> None:
        """Reload the saved login and reconnect. This is also the manual retry after a problem."""
        await self._cancel_task()
        await self._close_link()
        self._fatal = False
        self._task = asyncio.create_task(self._run(), name="direct-connection")

    async def _cancel_task(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _close_link(self) -> None:
        for unsubscribe in self._unsubscribe:
            with contextlib.suppress(Exception):
                unsubscribe()
        self._unsubscribe.clear()
        link, self._link = self._link, None
        if link is not None:
            with contextlib.suppress(Exception):
                await link.close()
        self._connected = False
        self._available = None

    async def _run(self) -> None:
        delay = MIN_RETRY
        while True:
            try:
                stored = load_session(self._settings.data_dir)
                if stored is None or not stored.has_login:
                    raise DirectProblem(f"Nav pieslēgts Ecovacs kontam. {LOGIN_HINT}")
                link = await self._connector.connect(stored, self._settings.ecovacs_device)
                self._link = link
                await self._attach(link)
                self._connected = True
                self._problem = None
                self._last_error_text = None
                delay = MIN_RETRY
                await self._rebuild()
                await self._heartbeat_loop(link.device)
                raise ConnectionError("heartbeat loop ended")  # not reached normally
            except asyncio.CancelledError:
                raise
            except DirectProblem as err:
                await self._stop_with(str(err))
                return
            except AuthenticationError as err:
                # Never retried automatically: repeated bad logins can lock the account.
                _LOGGER.warning("Ecovacs authentication failed: %s", type(err).__name__)
                await self._stop_with(
                    "Ecovacs nepieņēma saglabāto pieteikšanos (tā var būt beigusies). " + LOGIN_HINT
                )
                return
            except (DeebotError, aiohttp.ClientError, OSError, TimeoutError, ConnectionError) as err:
                self._last_error_text = type(err).__name__
                self._problem = "Nav savienojuma ar Ecovacs serveri. Mēģina vēlreiz…"
                _LOGGER.warning("Ecovacs connection problem: %s", type(err).__name__)
            except Exception:
                self._last_error_text = "unexpected"
                self._problem = "Neparedzēta kļūda savienojumā ar Ecovacs."
                _LOGGER.exception("Unexpected direct-mode error")
            finally:
                await self._close_link()
                if not self._fatal:
                    await self._rebuild()
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_RETRY)

    async def _stop_with(self, message: str) -> None:
        self._fatal = True
        self._problem = message
        self._last_error_text = message
        await self._rebuild()

    async def _heartbeat_loop(self, device: Device) -> None:
        """Ask the robot for its battery now and then. A reply proves it is reachable."""
        get = device.capabilities.battery.get[0]
        while True:
            try:
                if await device.execute_command(get):
                    self._available = True
                    await self._touch()
            except Exception:
                _LOGGER.debug("Heartbeat failed", exc_info=True)
            await asyncio.sleep(HEARTBEAT_SECONDS)

    # --- events -----------------------------------------------------------------
    async def _attach(self, link: Link) -> None:
        device = link.device
        caps = device.capabilities
        bus = device.events
        info = device.device_info
        self._robot_name = _label(info)
        self._model = str(info.get("deviceName") or info.get("class") or "")
        self._limits = {}

        def on(event_type: Any, handler: Callable[[Any], Awaitable[None]]) -> None:
            self._unsubscribe.append(bus.subscribe(event_type, handler))

        async def seen(update: Callable[[], None]) -> None:
            update()
            await self._touch()

        async def availability(e: AvailabilityEvent) -> None:
            self._available = e.available
            await self._rebuild()

        async def state(e: StateEvent) -> None:
            await seen(lambda: setattr(self, "_activity", _ACTIVITY.get(e.state, Activity.UNKNOWN)))

        async def battery(e: BatteryEvent) -> None:
            await seen(lambda: setattr(self, "_battery", int(e.value)))

        async def fan(e: FanSpeedEvent) -> None:
            await seen(lambda: setattr(self, "_fan_speed", e.speed.name.lower()))

        async def work_mode(e: WorkModeEvent) -> None:
            await seen(lambda: setattr(self, "_work_mode", e.mode.name.lower()))

        async def error(e: ErrorEvent) -> None:
            await seen(lambda: setattr(self, "_error", translate_error(int(e.code), e.description)))

        async def stats(e: StatsEvent) -> None:
            def update() -> None:
                self._area = None if e.area is None else float(e.area)
                self._minutes = None if e.time is None else round(e.time / 60, 1)

            await seen(update)

        async def report(e: ReportStatsEvent) -> None:
            await seen(lambda: None)
            if e.status in (CleanJobStatus.NO_STATUS, CleanJobStatus.CLEANING):
                return  # only a finished job is an event worth reporting
            await self._emit("job_finished", {"result": e.status.name.lower()})

        async def rooms(e: RoomsEvent) -> None:
            await seen(lambda: setattr(self, "_rooms", numbered_rooms(list(e.rooms))))

        async def maps(e: CachedMapInfoEvent) -> None:
            def update() -> None:
                self._maps = {
                    (m.name or _UNNAMED_MAP.format(id=m.id)): m.id
                    for m in sorted(e.maps, key=lambda m: (m.name or "", m.id))
                }
                using = next((m for m in e.maps if m.using), None)
                if using is not None:
                    self._active_map_id = using.id

            await seen(update)

        async def major_map(e: MajorMapEvent) -> None:
            await seen(lambda: setattr(self, "_active_map_id", e.map_id))

        async def map_changed(e: MapChangedEvent) -> None:
            await seen(lambda: setattr(self, "_map_updated", e.when))

        async def station(e: StationEvent) -> None:
            await seen(lambda: setattr(self, "_station", e.state.name.lower()))

        def value_handler(key: str, getter: Callable[[Any], Any]) -> Callable[[Any], Awaitable[None]]:
            async def handler(e: Any) -> None:
                await seen(lambda: self._values.__setitem__(key, getter(e)))

            return handler

        on(AvailabilityEvent, availability)
        on(StateEvent, state)
        on(BatteryEvent, battery)
        on(ErrorEvent, error)
        on(StatsEvent, stats)
        on(ReportStatsEvent, report)
        if caps.fan_speed:
            on(FanSpeedEvent, fan)
        if caps.clean.work_mode:
            on(WorkModeEvent, work_mode)
        if caps.station:
            on(StationEvent, station)
        if caps.map:
            on(RoomsEvent, rooms)
            on(CachedMapInfoEvent, maps)
            on(MapChangedEvent, map_changed)  # also switches the library's map rendering on
            if isinstance(caps.map.major, CapabilitySet):
                on(MajorMapEvent, major_map)
        if caps.settings.carpet_auto_fan_boost:
            on(CarpetAutoFanBoostEvent, value_handler("carpet_auto_fan_boost", lambda e: e.enabled))
        if caps.clean.continuous:
            on(ContinuousCleaningEvent, value_handler("continuous_cleaning", lambda e: e.enabled))
        if caps.settings.child_lock:
            on(ChildLockEvent, value_handler("child_lock", lambda e: e.enabled))
        if caps.settings.volume:
            self._limits["volume"] = (0, 10, 1)
            on(VolumeEvent, value_handler("volume", lambda e: e.volume))
        if caps.clean.count:
            self._limits["clean_count"] = (1, 4, 1)
            on(CleanCountEvent, value_handler("clean_count", lambda e: e.count))
        if caps.water:
            amount = caps.water.amount
            if amount is not None and hasattr(amount, "min"):
                self._limits["water_amount"] = (amount.min, amount.max, 1)
                on(WaterCustomAmountEvent, value_handler("water_amount", lambda e: e.value))

    async def _touch(self) -> None:
        self._last_seen = datetime.now(UTC)
        await self._rebuild()

    async def _rebuild(self) -> None:
        async with self._rebuild_lock:
            await self._publish(self._build_snapshot())

    def _build_snapshot(self) -> RobotSnapshot:
        snap = RobotSnapshot(backend_connected=self._connected, connection_problem=self._problem)
        snap.robot_name, snap.model = self._robot_name, self._model
        if not self._connected or self._link is None:
            return snap  # nothing cached is shown as current
        device = self._link.device
        caps = device.capabilities

        snap.robot_available = self._available is True
        if not snap.robot_available:
            snap.connection_problem = (
                "Ecovacs mākonis vēl nav saņēmis atbildi no robota."
                if self._available is None
                else "Ecovacs mākonis nevar sazināties ar robotu."
            )
        snap.activity = self._activity
        snap.battery = self._battery
        if caps.fan_speed:
            snap.fan_speed = self._fan_speed
            snap.fan_speed_options = tuple(t.name.lower() for t in caps.fan_speed.types)
        if caps.clean.work_mode:
            snap.work_mode = self._work_mode
            snap.work_mode_options = tuple(t.name.lower() for t in caps.clean.work_mode.types)
        snap.rooms = self._rooms
        snap.map_options = tuple(self._maps)
        snap.active_map = next((lbl for lbl, mid in self._maps.items() if mid == self._active_map_id), None)
        snap.map_updated = self._map_updated
        snap.error = self._error
        if self._activity == Activity.ERROR and snap.error is None:
            snap.error = GENERIC_ERROR
        snap.station_state = self._station
        snap.last_clean_area = self._area
        snap.last_clean_minutes = self._minutes
        snap.last_update = self._last_seen

        for key, value in self._values.items():
            if value is None:
                continue
            if isinstance(value, bool):
                snap.settings[key] = Setting(key, "switch", value)
            else:
                lo, hi, step = self._limits.get(key, (0, 100, 1))
                snap.settings[key] = Setting(key, "number", value, lo, hi, step)

        area = caps.clean.action.area is not None
        snap.capabilities = {
            "start": True,
            "pause": True,
            "stop": True,
            "return_to_base": True,
            "locate": True,
            "fan_speed": caps.fan_speed is not None,
            "clean_rooms": area and bool(self._rooms),
            "clean_zone": area,
            "work_mode": caps.clean.work_mode is not None,
            "active_map": bool(caps.map and isinstance(caps.map.major, CapabilitySet) and self._maps),
            "map": caps.map is not None,
            "error_codes": True,
            "job_finished_event": True,
            "empty_dustbin": bool(
                caps.station and StationAction.EMPTY_DUSTBIN in caps.station.action.types
            ),
            "announcements": False,  # no text-to-speech without Home Assistant
        }
        return snap

    # --- commands -----------------------------------------------------------------
    async def _execute(self, command: Any) -> dict[str, Any]:
        if self._link is None or not self._connected:
            raise NotConnectedError("Nav savienojuma ar Ecovacs serveri.")
        try:
            response = await self._link.device.execute_command(command)
        except DeebotError as err:
            raise AdapterError("Ecovacs atteicās izpildīt komandu.", type(err).__name__) from err
        if response:
            self._available = True
            await self._touch()
        elif self._available is False:
            raise AdapterError("Robots nav sasniedzams. Komanda netika izpildīta.", "unreachable")
        else:
            # The library hides failures (it returns an empty answer). State verification
            # decides whether the robot really reacted, so this is not reported as success.
            _LOGGER.warning("Empty answer to %s", getattr(command, "NAME", type(command).__name__))
        return response

    def _caps(self) -> Any:
        if self._link is None or not self._connected:
            raise NotConnectedError("Nav savienojuma ar Ecovacs serveri.")
        return self._link.device.capabilities

    async def send(self, request: CommandRequest) -> None:
        caps = self._caps()
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
            case CommandName.CLEAN_ROOMS | CommandName.CLEAN_ZONE:
                if action.area is None:
                    raise UnsupportedError("Šī funkcija jūsu robotam nav pieejama.")
                if name == CommandName.CLEAN_ROOMS:
                    # A LIST: the library joins it. A pre-joined string would be split per character.
                    await self._execute(
                        action.area(CleanMode.SPOT_AREA, [int(r) for r in params["rooms"]], params["cleanings"])
                    )
                else:
                    await self._execute(
                        action.area(CleanMode.CUSTOM_AREA, [int(c) for c in params["coordinates"]],
                                    params["cleanings"])
                    )
            case CommandName.SET_FAN_SPEED:
                if not caps.fan_speed:
                    raise UnsupportedError("Šī funkcija jūsu robotam nav pieejama.")
                await self._execute(caps.fan_speed.set(FanSpeedLevel[params["value"].upper()]))
            case CommandName.SET_WORK_MODE:
                if not caps.clean.work_mode:
                    raise UnsupportedError("Šī funkcija jūsu robotam nav pieejama.")
                await self._execute(caps.clean.work_mode.set(WorkMode[params["value"].upper()]))
            case CommandName.SET_ACTIVE_MAP:
                map_id = self._maps.get(params["value"])
                if map_id is None or not caps.map or not isinstance(caps.map.major, CapabilitySet):
                    raise UnsupportedError("Šī karte nav pieejama.")
                await self._execute(caps.map.major.set(map_id))
            case CommandName.SET_SETTING:
                await self._execute(self._setting_command(caps, params["key"], params["value"]))
            case CommandName.EMPTY_DUSTBIN:
                if not (caps.station and StationAction.EMPTY_DUSTBIN in caps.station.action.types):
                    raise UnsupportedError("Šī funkcija jūsu robotam nav pieejama.")
                await self._execute(caps.station.action.execute(StationAction.EMPTY_DUSTBIN))
            case CommandName.REFRESH_MAP:
                if self._link is None or self._link.device.map is None:
                    raise UnsupportedError("Karte nav pieejama.")
                try:
                    self._link.device.map.refresh()
                except MapError as err:
                    raise AdapterError("Neizdevās atjaunot karti.", str(err)) from err
            case _:
                raise UnsupportedError("Nezināma komanda.")

    @staticmethod
    def _setting_command(caps: Any, key: str, value: Any) -> Any:
        switches = {
            "carpet_auto_fan_boost": caps.settings.carpet_auto_fan_boost,
            "continuous_cleaning": caps.clean.continuous,
            "child_lock": caps.settings.child_lock,
        }
        numbers = {
            "volume": caps.settings.volume,
            "clean_count": caps.clean.count,
            "water_amount": caps.water.amount if caps.water else None,
        }
        if key in switches and switches[key] is not None:
            return switches[key].set(bool(value))
        if key in numbers and numbers[key] is not None:
            return numbers[key].set(int(value))
        raise UnsupportedError("Šis iestatījums nav pieejams.")

    # --- map ----------------------------------------------------------------------
    async def get_map_svg(self) -> bytes | None:
        if self._link is None or not self._connected or self._link.device.map is None:
            return None
        device_map = self._link.device.map
        try:
            svg = await asyncio.to_thread(device_map.get_svg_map)
        except MapError as err:
            raise AdapterError("Neizdevās ielādēt karti.", str(err)) from err
        return svg.encode() if svg else None

    # --- diagnostics ----------------------------------------------------------------
    async def diagnostics(self) -> dict[str, Any]:
        stored = load_session(self._settings.data_dir)
        try:
            library = version("deebot-client")
        except PackageNotFoundError:
            library = None
        return {
            "integration": "direct",
            "library": f"deebot-client {library}",
            "connected": self._connected,
            "robot_reachable": self._available,
            "problem": self._problem,
            "last_error": self._last_error_text,
            "login_saved": bool(stored and stored.has_login),
            "country": stored.country if stored else None,
            "robot": {"name": self._robot_name, "model": self._model,
                      "class": self._link.device.device_info.get("class") if self._link else None},
            "robots_on_account": self._link.candidates if self._link else [],
            "rooms": len(self._rooms),
            "maps": list(self._maps),
        }
