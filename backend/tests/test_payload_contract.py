"""The service payload must produce the right command inside the real deebot-client.

Skipped when deebot-client (Python 3.14 only) is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("deebot_client")

from deebot_client.commands.json.clean import CleanArea  # noqa: E402
from deebot_client.models import CleanMode  # noqa: E402

from app.adapters.homeassistant import HomeAssistantAdapter  # noqa: E402
from app.config import Settings  # noqa: E402
from app.models import CommandName, CommandRequest  # noqa: E402


class _Recorder(HomeAssistantAdapter):
    def __init__(self) -> None:
        super().__init__(Settings.from_env({"HA_URL": "http://x", "HA_TOKEN": "t", "AUTH_DISABLED": "1"}))
        self.calls: list[tuple[str, str, dict]] = []
        self._discovery.vacuum = "vacuum.test"

    async def _service(self, domain, service, data, timeout=None):  # type: ignore[override]
        self.calls.append((domain, service, data))


async def test_room_payload_becomes_correct_library_command():
    adapter = _Recorder()
    await adapter.send(CommandRequest(CommandName.CLEAN_ROOMS, {"rooms": ["12", "3"], "cleanings": 2}))
    params = adapter.calls[0][2]["params"]
    command = CleanArea(CleanMode.SPOT_AREA, params["rooms"], params["cleanings"])
    assert command._args["content"] == "12,3"
    assert command._args["count"] == 2


async def test_zone_payload_becomes_correct_library_command():
    adapter = _Recorder()
    await adapter.send(CommandRequest(CommandName.CLEAN_ZONE, {"coordinates": [-10, 20, 300, 400]}))
    params = adapter.calls[0][2]["params"]
    command = CleanArea(CleanMode.CUSTOM_AREA, params["coordinates"], params["cleanings"])
    assert command._args["content"] == "-10,20,300,400"
