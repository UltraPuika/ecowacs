"""Command safety: validation, duplicates, timeouts, failures and verification."""

from __future__ import annotations

import asyncio

import pytest

from app.adapters.base import AdapterError, UnsupportedError
from app.commands import CommandService
from app.models import Activity, CommandName, CommandRequest, CommandStatus
from app.storage import Storage

from .conftest import FakeAdapter


@pytest.fixture
async def service(fake_adapter: FakeAdapter) -> CommandService:
    await fake_adapter.start()
    return CommandService(
        fake_adapter, Storage(":memory:"), command_timeout=0.3, verify_timeout=0.3,
        dedupe_window=1.0, setting_verify_timeout=0.2,
    )


async def test_start_confirmed_only_after_state_changes(service, fake_adapter):
    result = await service.execute(CommandRequest(CommandName.START))
    assert result.status == CommandStatus.CONFIRMED
    assert result.message == "Robots sāka tīrīšanu."
    assert fake_adapter.snapshot.activity == Activity.CLEANING


async def test_sent_but_not_confirmed_is_reported_honestly(service, fake_adapter):
    fake_adapter.react = False
    result = await service.execute(CommandRequest(CommandName.START))
    assert result.status == CommandStatus.SENT
    assert "nav apstiprinājis" in result.message


async def test_concurrent_duplicate_start_is_sent_once(service, fake_adapter):
    fake_adapter.send_delay = 0.1
    results = await asyncio.gather(
        *(service.execute(CommandRequest(CommandName.START)) for _ in range(5))
    )
    assert len(fake_adapter.sent) == 1
    statuses = sorted(r.status for r in results)
    assert statuses.count(CommandStatus.REJECTED) == 4


async def test_repeat_within_dedupe_window_rejected(service, fake_adapter):
    await service.execute(CommandRequest(CommandName.LOCATE))
    second = await service.execute(CommandRequest(CommandName.LOCATE))
    assert second.status == CommandStatus.REJECTED
    assert len(fake_adapter.sent) == 1


async def test_other_motion_command_blocked_while_one_in_flight(service, fake_adapter):
    fake_adapter.send_delay = 0.1
    first = asyncio.create_task(service.execute(CommandRequest(CommandName.START)))
    await asyncio.sleep(0.02)
    second = await service.execute(CommandRequest(CommandName.RETURN_TO_BASE))
    assert second.status == CommandStatus.REJECTED
    assert (await first).status == CommandStatus.CONFIRMED


async def test_timeout_reports_failure(service, fake_adapter):
    fake_adapter.send_delay = 1.0
    result = await service.execute(CommandRequest(CommandName.START))
    assert result.status == CommandStatus.FAILED
    assert "neatbildēja" in result.message


async def test_adapter_error_reports_failure_and_callback(service, fake_adapter):
    fake_adapter.fail_with = AdapterError("Home Assistant atteicās izpildīt komandu.", "x")
    seen = []

    async def on_failed(request, message):
        seen.append(request.name)

    service.on_failure(on_failed)
    result = await service.execute(CommandRequest(CommandName.START))
    assert result.status == CommandStatus.FAILED
    assert seen == [CommandName.START]


async def test_unsupported_capability_is_not_sent(service, fake_adapter):
    caps = dict(fake_adapter.snapshot.capabilities, clean_zone=False)
    await fake_adapter.set(capabilities=caps)
    result = await service.execute(
        CommandRequest(CommandName.CLEAN_ZONE, {"coordinates": [0, 0, 10, 10]})
    )
    assert result.status == CommandStatus.REJECTED
    assert fake_adapter.sent == []


async def test_unsupported_error_from_adapter_is_rejection(service, fake_adapter):
    fake_adapter.fail_with = UnsupportedError("Šī funkcija jūsu robotam nav pieejama.")
    result = await service.execute(CommandRequest(CommandName.EMPTY_DUSTBIN))
    assert result.status == CommandStatus.REJECTED


async def test_not_connected_rejects_without_sending(service, fake_adapter):
    await fake_adapter.set(backend_connected=False)
    result = await service.execute(CommandRequest(CommandName.START))
    assert result.status == CommandStatus.REJECTED
    assert fake_adapter.sent == []


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"rooms": []},
        {"rooms": ["99"]},
        {"rooms": ["1", "1"]},
        {"rooms": ["1"], "cleanings": 3},
        {"rooms": "1"},
    ],
)
async def test_room_validation(service, fake_adapter, params):
    result = await service.execute(CommandRequest(CommandName.CLEAN_ROOMS, params))
    assert result.status == CommandStatus.REJECTED
    assert fake_adapter.sent == []


async def test_room_clean_normalised(service, fake_adapter):
    result = await service.execute(
        CommandRequest(CommandName.CLEAN_ROOMS, {"rooms": ["2", "1"], "cleanings": 2})
    )
    assert result.status == CommandStatus.CONFIRMED
    assert fake_adapter.sent[0].params == {"rooms": ["2", "1"], "cleanings": 2}
    assert service.last_start is not None


@pytest.mark.parametrize(
    "coords", [[0, 0, 0, 10], [10, 0, 0, 10], [0, 0, 10], [0, 0, 10, 10.5], [0, 0, 10, 10**7]]
)
async def test_zone_validation(service, fake_adapter, coords):
    result = await service.execute(CommandRequest(CommandName.CLEAN_ZONE, {"coordinates": coords}))
    assert result.status == CommandStatus.REJECTED


async def test_setting_validation(service, fake_adapter):
    bad = [
        {"key": "unknown", "value": True},
        {"key": "child_lock", "value": "yes"},
        {"key": "volume", "value": 99},
        {"key": "volume", "value": True},
    ]
    for params in bad:
        result = await service.execute(CommandRequest(CommandName.SET_SETTING, params))
        assert result.status == CommandStatus.REJECTED, params
    assert fake_adapter.sent == []


async def test_fan_speed_choice_validated_and_verified(service, fake_adapter):
    bad = await service.execute(CommandRequest(CommandName.SET_FAN_SPEED, {"value": "turbo"}))
    assert bad.status == CommandStatus.REJECTED
    ok = await service.execute(CommandRequest(CommandName.SET_FAN_SPEED, {"value": "max"}))
    assert ok.status == CommandStatus.CONFIRMED


async def test_unexpected_params_rejected(service):
    result = await service.execute(CommandRequest(CommandName.STOP, {"evil": 1}))
    assert result.status == CommandStatus.REJECTED


async def test_commands_are_logged(service, fake_adapter):
    await service.execute(CommandRequest(CommandName.LOCATE))
    log = service._storage.commands()
    assert log[0]["name"] == "locate"
    assert log[0]["status"] == "done"
