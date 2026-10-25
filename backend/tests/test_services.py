"""Announcements, history tracking, freshness and event log."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.base import AdapterError
from app.commands import CommandService
from app.errors_lv import translate_error
from app.models import Activity, CommandName, CommandRequest
from app.services import (
    AnnouncementSettings,
    Announcer,
    EventLog,
    HistoryTracker,
    freshness,
    join_lv,
)
from app.storage import Storage

from .conftest import FakeAdapter, make_snapshot

ENABLED = {"enabled": True, "tts_entity": "tts.piper", "media_player": "media_player.virtuve"}


@pytest.fixture
async def env(fake_adapter: FakeAdapter):
    await fake_adapter.start()
    storage = Storage(":memory:")
    commands = CommandService(fake_adapter, storage, 0.3, 0.3, 1.0)
    announcer = Announcer(storage, fake_adapter, commands, dedupe_seconds=60)
    history = HistoryTracker(storage, commands, fake_adapter, stats_delay=0)
    fake_adapter.add_listener(announcer.on_snapshot)
    fake_adapter.add_listener(history.on_snapshot)
    fake_adapter.add_event_listener(announcer.on_event)
    fake_adapter.add_event_listener(history.on_event)
    return fake_adapter, storage, commands, announcer


async def settle():
    for _ in range(5):
        await asyncio.sleep(0.01)


def test_join_lv():
    assert join_lv(["Virtuve"]) == "Virtuve"
    assert join_lv(["A", "B", "C"]) == "A, B un C"


async def test_disabled_by_default(env):
    adapter, storage, _, announcer = env
    await adapter.set(activity=Activity.CLEANING)
    await settle()
    assert adapter.spoken == []


async def test_room_start_announcement(env):
    adapter, storage, commands, announcer = env
    announcer.save(AnnouncementSettings.from_dict(ENABLED))
    await commands.execute(CommandRequest(CommandName.CLEAN_ROOMS, {"rooms": ["1", "2"]}))
    await settle()
    assert adapter.spoken[-1][2] == "Sāku tīrīšanu: Virtuve un Gaitenis."


async def test_no_duplicate_announcements(env):
    adapter, _, _, announcer = env
    announcer.save(AnnouncementSettings.from_dict(ENABLED))
    for _ in range(3):
        await adapter.set(activity=Activity.RETURNING)
        await adapter.set(activity=Activity.CLEANING)
    await settle()
    texts = [s[2] for s in adapter.spoken]
    assert texts.count("Robots atgriežas uz uzlādes staciju.") == 1


async def test_no_announcement_on_reconnect(env):
    adapter, _, _, announcer = env
    announcer.save(AnnouncementSettings.from_dict(ENABLED))
    await adapter.set(backend_connected=False, activity=Activity.UNKNOWN)
    await adapter.set(backend_connected=True, activity=Activity.CLEANING)
    await settle()
    assert adapter.spoken == []


async def test_stuck_error_announcement(env):
    adapter, _, _, announcer = env
    announcer.save(AnnouncementSettings.from_dict(ENABLED))
    await adapter.set(activity=Activity.ERROR, error=translate_error(105))
    await settle()
    assert adapter.spoken[-1][2] == "Robots ir iestrēdzis. Lūdzu, pārbaudiet tā atrašanās vietu."


async def test_finished_only_from_reliable_event(env):
    adapter, storage, _, announcer = env
    announcer.save(AnnouncementSettings.from_dict(ENABLED))
    await adapter.set(activity=Activity.DOCKED)
    await settle()
    assert not any("pabeigta" in s[2] for s in adapter.spoken)
    await adapter.emit("job_finished", {"result": "finished"})
    await settle()
    assert adapter.spoken[-1][2] == "Tīrīšana ir pabeigta."
    await adapter.emit("job_finished", {"result": "manually_stopped"})
    await settle()
    assert [s[2] for s in adapter.spoken].count("Tīrīšana ir pabeigta.") == 1


async def test_failed_start_announced(env):
    adapter, _, commands, announcer = env
    announcer.save(AnnouncementSettings.from_dict(ENABLED))
    adapter.fail_with = AdapterError("x")
    await commands.execute(CommandRequest(CommandName.START))
    await settle()
    assert adapter.spoken[-1][2].startswith("Neizdevās sākt tīrīšanu.")


async def test_per_event_toggle(env):
    adapter, _, _, announcer = env
    announcer.save(AnnouncementSettings.from_dict({**ENABLED, "events": {"returning": False}}))
    await adapter.set(activity=Activity.RETURNING)
    await settle()
    assert adapter.spoken == []


async def test_speaker_failure_logged_not_raised(env):
    adapter, storage, _, announcer = env
    adapter.speak_error = AdapterError("Home Assistant atteicās izpildīt komandu.")
    problems = await announcer.test(AnnouncementSettings.from_dict(ENABLED))
    assert problems and storage.events()[0]["level"] == "warning"


async def test_history_session_lifecycle(env):
    adapter, storage, commands, _ = env
    await commands.execute(CommandRequest(CommandName.CLEAN_ROOMS, {"rooms": ["2"]}))
    await settle()
    session = storage.sessions()[0]
    assert session["kind"] == "rooms" and session["rooms"] == ["Gaitenis"]
    assert session["started_by"] == "app" and session["ended_at"] is None
    await adapter.set(last_clean_area=7.5, last_clean_minutes=12)
    await adapter.emit("job_finished", {"result": "finished"})
    await settle()
    session = storage.sessions()[0]
    assert session["result"] == "finished" and session["area_m2"] == 7.5


async def test_history_session_started_elsewhere(env):
    adapter, storage, _, _ = env
    await adapter.set(activity=Activity.CLEANING)
    assert storage.sessions()[0]["started_by"] == "robot"


async def test_history_without_job_event_closes_on_dock(env):
    adapter, storage, _, _ = env
    caps = dict(adapter.snapshot.capabilities, job_finished_event=False)
    await adapter.set(capabilities=caps, activity=Activity.CLEANING)
    await adapter.set(activity=Activity.DOCKED)
    assert storage.sessions()[0]["result"] == "unknown"


def test_freshness():
    now = datetime.now(UTC)
    assert freshness(make_snapshot(), now, 900)["stale"] is False
    old = make_snapshot(last_update=now - timedelta(hours=1))
    assert freshness(old, now, 900)["stale"] is True
    assert freshness(make_snapshot(robot_available=False), now, 900)["stale"] is True
    assert freshness(make_snapshot(last_update=None), now, 900)["stale"] is True
    demo = make_snapshot(demo=True, last_update=now - timedelta(days=1))
    assert freshness(demo, now, 900)["stale"] is False


def test_event_log():
    storage = Storage(":memory:")
    log = EventLog(storage)
    a = make_snapshot()
    log.on_snapshot(a, replace(a, backend_connected=False, connection_problem="Nav savienojuma"))
    log.on_snapshot(a, replace(a, error=translate_error(114)))
    kinds = [e["kind"] for e in storage.events()]
    assert kinds == ["robot_error", "connection"]


def test_announcement_settings_validation():
    with pytest.raises(ValueError):
        AnnouncementSettings.from_dict({"enabled": True}).validate()
    with pytest.raises(ValueError):
        AnnouncementSettings.from_dict({**ENABLED, "volume": 3}).validate()
    with pytest.raises(ValueError):
        AnnouncementSettings.from_dict({**ENABLED, "language": "lv;rm -rf"}).validate()
    AnnouncementSettings.from_dict({"enabled": True, "notify_service": "notify.mobile_app_x"}).validate()
