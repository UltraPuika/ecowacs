"""Data models shared by adapters, services and the API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Activity(StrEnum):
    """Robot activity, independent of the integration."""

    CLEANING = "cleaning"
    PAUSED = "paused"
    RETURNING = "returning"
    DOCKED = "docked"
    IDLE = "idle"
    ERROR = "error"
    UNKNOWN = "unknown"


class CommandName(StrEnum):
    """Commands the frontend may request."""

    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    RETURN_TO_BASE = "return_to_base"
    LOCATE = "locate"
    CLEAN_ROOMS = "clean_rooms"
    CLEAN_ZONE = "clean_zone"
    SET_WORK_MODE = "set_work_mode"
    SET_FAN_SPEED = "set_fan_speed"
    SET_ACTIVE_MAP = "set_active_map"
    SET_SETTING = "set_setting"
    EMPTY_DUSTBIN = "empty_dustbin"
    REFRESH_MAP = "refresh_map"


# Commands that physically move the robot. Only one may be in flight at a time.
MOTION_COMMANDS = frozenset(
    {
        CommandName.START,
        CommandName.PAUSE,
        CommandName.RESUME,
        CommandName.STOP,
        CommandName.RETURN_TO_BASE,
        CommandName.CLEAN_ROOMS,
        CommandName.CLEAN_ZONE,
    }
)

# Activities that confirm a motion command took effect.
EXPECTED_ACTIVITIES: dict[CommandName, frozenset[Activity]] = {
    CommandName.START: frozenset({Activity.CLEANING}),
    CommandName.CLEAN_ROOMS: frozenset({Activity.CLEANING}),
    CommandName.CLEAN_ZONE: frozenset({Activity.CLEANING}),
    CommandName.RESUME: frozenset({Activity.CLEANING}),
    CommandName.PAUSE: frozenset({Activity.PAUSED}),
    CommandName.STOP: frozenset({Activity.IDLE, Activity.DOCKED, Activity.RETURNING}),
    CommandName.RETURN_TO_BASE: frozenset({Activity.RETURNING, Activity.DOCKED}),
}


@dataclass(frozen=True)
class Room:
    """A room on the active map."""

    id: str
    name: str


@dataclass(frozen=True)
class ErrorInfo:
    """A robot error translated to Latvian."""

    code: int
    title: str
    explanation: str
    action: str
    original: str | None = None


@dataclass(frozen=True)
class Setting:
    """A robot setting the UI can show and change."""

    key: str
    kind: str  # "switch", "number" or "select"
    value: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: tuple[str, ...] = ()


@dataclass
class RobotSnapshot:
    """Everything the UI needs to know about the robot at one moment."""

    backend_connected: bool = False
    robot_available: bool = False
    activity: Activity = Activity.UNKNOWN
    battery: int | None = None
    fan_speed: str | None = None
    fan_speed_options: tuple[str, ...] = ()
    work_mode: str | None = None
    work_mode_options: tuple[str, ...] = ()
    rooms: tuple[Room, ...] = ()
    active_map: str | None = None
    map_options: tuple[str, ...] = ()
    map_updated: datetime | None = None
    error: ErrorInfo | None = None
    station_state: str | None = None
    last_clean_area: float | None = None
    last_clean_minutes: float | None = None
    settings: dict[str, Setting] = field(default_factory=dict)
    capabilities: dict[str, bool] = field(default_factory=dict)
    last_update: datetime | None = None
    robot_name: str | None = None
    model: str | None = None
    connection_problem: str | None = None
    demo: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-friendly data."""
        data = asdict(self)
        data["activity"] = self.activity.value
        for key in ("map_updated", "last_update"):
            value = getattr(self, key)
            data[key] = value.isoformat() if value else None
        return data


@dataclass(frozen=True)
class CommandRequest:
    """A validated command request."""

    name: CommandName
    params: dict[str, Any] = field(default_factory=dict)

    def dedupe_key(self) -> str:
        """Identity used to detect duplicate submissions."""
        items = sorted((k, repr(v)) for k, v in self.params.items())
        return f"{self.name.value}:{items}"


class CommandStatus(StrEnum):
    """Outcome of a command."""

    CONFIRMED = "confirmed"  # robot state verified the effect
    SENT = "sent"  # integration accepted it, robot state did not confirm (yet)
    DONE = "done"  # non-motion command accepted by integration
    FAILED = "failed"
    REJECTED = "rejected"  # not sent: duplicate, busy or unsupported


@dataclass(frozen=True)
class CommandResult:
    """Result returned to the frontend."""

    status: CommandStatus
    message: str
    command: str

    def to_dict(self) -> dict[str, Any]:
        """Serialise."""
        return {"status": self.status.value, "message": self.message, "command": self.command}
