"""Adapter interface between the app and whatever controls the robot."""

from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..models import CommandRequest, RobotSnapshot

_LOGGER = logging.getLogger(__name__)

SnapshotListener = Callable[[RobotSnapshot, RobotSnapshot], Awaitable[None] | None]
EventListener = Callable[[str, dict[str, Any]], Awaitable[None] | None]


class AdapterError(Exception):
    """A command or query failed. ``user_message`` is shown to the user (Latvian)."""

    def __init__(self, user_message: str, detail: str | None = None) -> None:
        super().__init__(detail or user_message)
        self.user_message = user_message
        self.detail = detail


class UnsupportedError(AdapterError):
    """The robot or integration does not support the request."""


class NotConnectedError(AdapterError):
    """The integration is not connected."""


@dataclass(frozen=True)
class SpeechTargets:
    """Available text-to-speech and notification targets."""

    tts_entities: tuple[str, ...] = ()
    media_players: tuple[str, ...] = ()
    notify_services: tuple[str, ...] = ()


class RobotAdapter(ABC):
    """Base class. Subclasses publish snapshots and execute commands."""

    is_demo = False

    def __init__(self) -> None:
        self._snapshot = RobotSnapshot(demo=self.is_demo)
        self._listeners: list[SnapshotListener] = []
        self._event_listeners: list[EventListener] = []

    @property
    def snapshot(self) -> RobotSnapshot:
        """Latest known robot state."""
        return self._snapshot

    def add_listener(self, listener: SnapshotListener) -> None:
        """Register a callback for snapshot changes: ``listener(old, new)``."""
        self._listeners.append(listener)

    def add_event_listener(self, listener: EventListener) -> None:
        """Register a callback for discrete robot events (e.g. job finished)."""
        self._event_listeners.append(listener)

    async def _publish(self, snapshot: RobotSnapshot) -> None:
        old = self._snapshot
        self._snapshot = snapshot
        for listener in list(self._listeners):
            await _call_safely(listener, old, snapshot)

    async def _emit(self, name: str, data: dict[str, Any]) -> None:
        for listener in list(self._event_listeners):
            await _call_safely(listener, name, data)

    @abstractmethod
    async def start(self) -> None:
        """Connect and start receiving updates (must not block)."""

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect."""

    @abstractmethod
    async def send(self, request: CommandRequest) -> None:
        """Send a command. Raises AdapterError on failure."""

    @abstractmethod
    async def get_map_svg(self) -> bytes | None:
        """Return the current map as SVG bytes, or None if there is no map."""

    def map_rotation(self) -> int | None:
        """Clockwise rotation (0/90/180/270) of the map SVG, or None if map coordinates are unknown."""
        return None

    @abstractmethod
    async def diagnostics(self) -> dict[str, Any]:
        """Return diagnostic data. Must not contain secrets."""

    async def speech_targets(self) -> SpeechTargets:
        """Return available speech targets."""
        return SpeechTargets()

    async def speak(
        self,
        tts_entity: str,
        media_player: str,
        message: str,
        language: str | None,
        volume: float | None,
    ) -> None:
        """Speak a message on a speaker."""
        raise UnsupportedError("Paziņojumi nav pieejami šajā režīmā.")

    async def notify(self, service: str, message: str) -> None:
        """Send a phone notification."""
        raise UnsupportedError("Paziņojumi nav pieejami šajā režīmā.")


async def _call_safely(func: Callable[..., Any], *args: Any) -> None:
    try:
        result = func(*args)
        if inspect.isawaitable(result):
            await result
    except Exception:  # a broken listener must not stop the others
        _LOGGER.exception("Listener failed")
