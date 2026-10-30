"""Saved Ecovacs session: no password, owner-only file, tolerant reads."""

from __future__ import annotations

import stat

import pytest

from app.ecovacs_session import (
    SESSION_FILE,
    StoredSession,
    load_session,
    new_device_id,
    save_session,
    valid_country,
)


def test_roundtrip_and_permissions(tmp_path):
    save_session(tmp_path, StoredSession("AB12CD34", "LV", "uid-1", "tok-secret"))
    loaded = load_session(tmp_path)
    assert loaded == StoredSession("AB12CD34", "LV", "uid-1", "tok-secret")
    assert loaded.has_login
    assert stat.S_IMODE((tmp_path / SESSION_FILE).stat().st_mode) == 0o600
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".session-")]  # no temp leftovers


def test_token_not_in_repr():
    assert "tok-secret" not in repr(StoredSession("A", "LV", "u", "tok-secret"))


def test_missing_or_broken_file_is_none(tmp_path):
    assert load_session(tmp_path) is None
    (tmp_path / SESSION_FILE).write_text("{not json")
    assert load_session(tmp_path) is None
    (tmp_path / SESSION_FILE).write_text('{"device_id": "A", "country": "LATVIA"}')
    assert load_session(tmp_path) is None


def test_session_without_token_has_no_login():
    assert not StoredSession("A", "LV").has_login


def test_device_id_shape():
    ids = {new_device_id() for _ in range(50)}
    assert len(ids) > 40 and all(len(i) == 8 and i.isalnum() and i.upper() == i for i in ids)


@pytest.mark.parametrize("value,expected", [("lv", "LV"), (" DE ", "DE")])
def test_country_ok(value, expected):
    assert valid_country(value) == expected


@pytest.mark.parametrize("value", ["", "L", "LVA", "L1", None])
def test_country_invalid(value):
    with pytest.raises(ValueError):
        valid_country(value)
