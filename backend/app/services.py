"""Background services: freshness, history tracking, event log and announcements."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from .adapters.base import AdapterError, RobotAdapter
from .commands import START_COMMANDS, CommandService
from .models import Activity, CommandName, CommandRequest, RobotSnapshot
from .storage import Storage

_LOGGER = logging.getLogger(__name__)

ACTIVE = frozenset({Activity.CLEANING, Activity.PAUSED, Activity.RETURNING})
STUCK_CODES = frozenset({105, 408})
LAST_START_WINDOW = 120.0  # seconds: a start command this recent explains a new session


def freshness(snap: RobotSnapshot, now: datetime, stale_after: float) -> dict[str, Any]:
    """Decide whether the shown data can be trusted as current."""
    age = (now - snap.last_update).total_seconds() if snap.last_update else None
    reason = None
    if snap.demo:
        pass
    elif not snap.backend_connected:
        reason = (
            (snap.connection_problem or "Nav savienojuma ar robota serveri.")
            + " Rādītie dati var būt novecojuši."
        )
    elif not snap.robot_available:
        reason = "Nav savienojuma ar robotu. Rādītie dati var būt novecojuši."
    elif age is None:
        reason = "Robots vēl nav atsūtījis datus."
    elif age > stale_after:
        reason = "Robots ilgi nav sūtījis jaunus datus. Rādītie dati var būt novecojuši."
    return {"stale": reason is not None, "reason": reason, "age_seconds": age}


def join_lv(names: list[str]) -> str:
    """Join names the Latvian way: "A, B un C"."""
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " un " + names[-1]


def _recent_start(commands: CommandService) -> CommandRequest | None:
    if commands.last_start and time.monotonic() - commands.last_start[0] < LAST_START_WINDOW:
        return commands.last_start[1]
    return None


class EventLog:
    """Records connection changes and robot errors in the event log."""

    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def on_snapshot(self, old: RobotSnapshot, new: RobotSnapshot) -> None:
        if old.backend_connected != new.backend_connected:
            if new.backend_connected:
                self._storage.add_event("info", "connection", "Savienojums atjaunots.")
            else:
                self._storage.add_event(
                    "warning", "connection", new.connection_problem or "Savienojums pārtrūka."
                )
        elif new.backend_connected and old.robot_available != new.robot_available:
            if new.robot_available:
                self._storage.add_event("info", "connection", "Robots atkal ir sasniedzams.")
            else:
                self._storage.add_event("warning", "connection", "Robots nav sasniedzams.")
        if new.error and (old.error is None or old.error.code != new.error.code):
            self._storage.add_event(
                "error", "robot_error", f"{new.error.title} (kods {new.error.code})"
            )


class HistoryTracker:
    """Builds the local cleaning history from observed state changes."""

    def __init__(self, storage: Storage, commands: CommandService, adapter: RobotAdapter,
                 stats_delay: float = 5.0) -> None:
        self._storage = storage
        self._commands = commands
        self._adapter = adapter
        self._stats_delay = stats_delay
        self._tasks: set[asyncio.Task[None]] = set()

    def on_snapshot(self, old: RobotSnapshot, new: RobotSnapshot) -> None:
        if not new.backend_connected:
            return
        open_id = self._storage.open_session_id()
        if new.activity == Activity.CLEANING and old.activity not in ACTIVE and open_id is None:
            request = _recent_start(self._commands)
            if request is None:
                self._storage.open_session("whole", None, "robot")
            elif request.name == CommandName.CLEAN_ROOMS:
                names = {r.id: r.name for r in new.rooms}
                rooms = [names.get(r, r) for r in request.params["rooms"]]
                self._storage.open_session("rooms", rooms, "app")
            elif request.name == CommandName.CLEAN_ZONE:
                self._storage.open_session("zone", None, "app")
            else:
                self._storage.open_session("whole", None, "app")
        elif (
            open_id is not None
            and not new.capabilities.get("job_finished_event")
            and old.activity in ACTIVE
            and new.activity in (Activity.DOCKED, Activity.IDLE)
        ):
            # Without the "Last job" entity we can only guess the end of a job.
            self._storage.close_session(
                open_id, "unknown", new.last_clean_area, new.last_clean_minutes
            )

    def on_event(self, name: str, data: dict[str, Any]) -> None:
        if name != "job_finished":
            return
        task = asyncio.create_task(self._close_after_stats(str(data.get("result") or "unknown")))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _close_after_stats(self, result: str) -> None:
        await asyncio.sleep(self._stats_delay)  # area/time sensors update around the same time
        if (open_id := self._storage.open_session_id()) is not None:
            snap = self._adapter.snapshot
            self._storage.close_session(open_id, result, snap.last_clean_area, snap.last_clean_minutes)


@dataclass
class AnnouncementSettings:
    """User-editable announcement settings."""

    enabled: bool = False
    tts_entity: str = ""
    media_player: str = ""
    language: str = ""
    volume: float | None = None
    notify_service: str = ""
    events: dict[str, bool] = field(
        default_factory=lambda: {
            "started": True,
            "finished": True,
            "returning": True,
            "error": True,
            "command_failed": True,
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AnnouncementSettings:
        base = cls()
        if not data:
            return base
        events = {**base.events, **{k: bool(v) for k, v in (data.get("events") or {}).items() if k in base.events}}
        volume = data.get("volume")
        return cls(
            enabled=bool(data.get("enabled", False)),
            tts_entity=str(data.get("tts_entity") or ""),
            media_player=str(data.get("media_player") or ""),
            language=str(data.get("language") or ""),
            volume=float(volume) if isinstance(volume, (int, float)) and not isinstance(volume, bool) else None,
            notify_service=str(data.get("notify_service") or ""),
            events=events,
        )

    def validate(self) -> None:
        if self.tts_entity and not self.tts_entity.startswith("tts."):
            raise ValueError("TTS vienībai jāsākas ar tts.")
        if self.media_player and not self.media_player.startswith("media_player."):
            raise ValueError("Skaļrunim jāsākas ar media_player.")
        if self.notify_service and not self.notify_service.startswith("notify."):
            raise ValueError("Paziņojumu servisam jāsākas ar notify.")
        if self.volume is not None and not 0 <= self.volume <= 1:
            raise ValueError("Skaļumam jābūt no 0 līdz 1.")
        if self.language and (len(self.language) > 10 or not self.language.replace("_", "-").replace("-", "").isalpha()):
            raise ValueError("Nederīgs valodas kods.")
        if self.enabled and not ((self.tts_entity and self.media_player) or self.notify_service):
            raise ValueError("Izvēlieties skaļruni (TTS + atskaņotāju) vai tālruņa paziņojumus.")


MESSAGES = {
    "started": "Robots ir sācis tīrīšanu.",
    "finished": "Tīrīšana ir pabeigta.",
    "returning": "Robots atgriežas uz uzlādes staciju.",
    "stuck": "Robots ir iestrēdzis. Lūdzu, pārbaudiet tā atrašanās vietu.",
    "command_failed": "Neizdevās sākt tīrīšanu. Pārbaudiet savienojumu ar robotu.",
    "test": "Šis ir pārbaudes paziņojums no robota lietotnes.",
}


class Announcer:
    """Speaks Latvian announcements through Home Assistant, without repeating itself."""

    SETTINGS_KEY = "announcements"

    def __init__(self, storage: Storage, adapter: RobotAdapter, commands: CommandService,
                 dedupe_seconds: float = 300.0) -> None:
        self._storage = storage
        self._adapter = adapter
        self._commands = commands
        self._dedupe = dedupe_seconds
        self._last: dict[str, float] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        commands.on_failure(self._on_command_failed)

    @property
    def settings(self) -> AnnouncementSettings:
        return AnnouncementSettings.from_dict(self._storage.get_setting(self.SETTINGS_KEY))

    def save(self, settings: AnnouncementSettings) -> None:
        settings.validate()
        self._storage.set_setting(self.SETTINGS_KEY, asdict(settings))

    def message_for(self, old: RobotSnapshot, new: RobotSnapshot) -> tuple[str, str] | None:
        """Return (event, message) for a reliable state transition, else None."""
        if not (old.backend_connected and new.backend_connected and old.robot_available):
            return None  # never announce artefacts of (re)connecting
        if new.error and (old.error is None or old.error.code != new.error.code):
            if new.error.code in STUCK_CODES:
                return "error", MESSAGES["stuck"]
            return "error", f"Robotam nepieciešama uzmanība. {new.error.title}."
        if new.activity == Activity.CLEANING and old.activity in (Activity.DOCKED, Activity.IDLE):
            request = _recent_start(self._commands)
            if request and request.name == CommandName.CLEAN_ROOMS:
                names = {r.id: r.name for r in new.rooms}
                rooms = [names.get(r, r) for r in request.params["rooms"]]
                return "started", f"Sāku tīrīšanu: {join_lv(rooms)}."
            return "started", MESSAGES["started"]
        if new.activity == Activity.RETURNING and old.activity != Activity.RETURNING:
            return "returning", MESSAGES["returning"]
        return None

    def on_snapshot(self, old: RobotSnapshot, new: RobotSnapshot) -> None:
        if found := self.message_for(old, new):
            self._schedule(*found)

    def on_event(self, name: str, data: dict[str, Any]) -> None:
        if name == "job_finished" and data.get("result") in ("finished", "finished_with_warnings"):
            self._schedule("finished", MESSAGES["finished"])

    async def _on_command_failed(self, request: CommandRequest, _message: str) -> None:
        if request.name in START_COMMANDS:
            self._schedule("command_failed", MESSAGES["command_failed"])

    def _schedule(self, event: str, message: str) -> None:
        settings = self.settings
        if not settings.enabled or not settings.events.get(event, False):
            return
        now = time.monotonic()
        key = f"{event}:{message}"
        if now - self._last.get(key, -1e9) < self._dedupe:
            return
        self._last[key] = now
        task = asyncio.create_task(self._deliver(settings, message))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _deliver(self, settings: AnnouncementSettings, message: str) -> list[str]:
        problems = []
        if settings.tts_entity and settings.media_player:
            try:
                await self._adapter.speak(
                    settings.tts_entity, settings.media_player, message,
                    settings.language or None, settings.volume,
                )
            except AdapterError as err:
                problems.append(f"Skaļrunis: {err.user_message}")
        if settings.notify_service:
            try:
                await self._adapter.notify(settings.notify_service, message)
            except AdapterError as err:
                problems.append(f"Tālrunis: {err.user_message}")
        if problems:
            self._storage.add_event("warning", "announcement", "Paziņojums neizdevās. " + " ".join(problems))
        else:
            self._storage.add_event("info", "announcement", f"Paziņots: {message}")
        return problems

    async def test(self, settings: AnnouncementSettings) -> list[str]:
        """Deliver a test message now, ignoring the enabled flag and dedupe."""
        return await self._deliver(settings, MESSAGES["test"])
