"""Read-only checks against YOUR real Home Assistant and robot.

Skipped by default. Run them explicitly:

    REAL_HA_URL=http://192.168.1.10:8123 REAL_HA_TOKEN=... \
        python -m pytest -m realdevice -s

They only READ data: no cleaning, movement or settings commands are sent.
"""

from __future__ import annotations

import asyncio
import os

import pytest

from app.adapters.homeassistant import HomeAssistantAdapter
from app.config import Settings

pytestmark = pytest.mark.realdevice


@pytest.fixture
async def adapter():
    url, token = os.environ.get("REAL_HA_URL"), os.environ.get("REAL_HA_TOKEN")
    if not url or not token:
        pytest.skip("REAL_HA_URL and REAL_HA_TOKEN are not set")
    settings = Settings.from_env(
        {"MODE": "homeassistant", "HA_URL": url, "HA_TOKEN": token, "AUTH_DISABLED": "true",
         "HA_VACUUM_ENTITY": os.environ.get("REAL_HA_VACUUM_ENTITY", "")}
    )
    a = HomeAssistantAdapter(settings)
    await a.start()
    for _ in range(100):
        if a.snapshot.backend_connected and a.snapshot.robot_name:
            break
        await asyncio.sleep(0.1)
    yield a
    await a.stop()


async def test_robot_found_and_reports_state(adapter):
    snap = adapter.snapshot
    diag = await adapter.diagnostics()
    print("\nDiagnostics:", diag)
    print("Snapshot:", snap.to_dict())
    assert snap.backend_connected, diag
    assert diag["vacuum_entity"], diag["discovery_problem"]
    assert snap.robot_available, "Robot is unavailable in Home Assistant"
    assert snap.battery is not None


async def test_rooms_and_map(adapter):
    snap = adapter.snapshot
    print("\nRooms:", [(r.id, r.name) for r in snap.rooms])
    svg = await adapter.get_map_svg()
    assert svg is None or svg.lstrip().startswith(b"<svg")
