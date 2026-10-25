"""Config, Latvian error texts, redaction, auth tokens, storage, demo adapter."""

from __future__ import annotations

import asyncio
import logging
import re

import pytest

from app.adapters.demo import DemoAdapter
from app.auth import Authenticator, LoginRateLimiter, load_secret
from app.config import ConfigError, Settings
from app.errors_lv import known_codes, translate_error
from app.map_svg import render_map
from app.models import Activity, CommandName, CommandRequest
from app.redact import REDACTED, RedactingFilter, redact, redact_text
from app.storage import Storage

LATVIAN_LETTERS = re.compile(r"[āčēģīķļņšūž]", re.IGNORECASE)


def test_config_requires_password_or_explicit_opt_out():
    base = {"MODE": "homeassistant", "HA_URL": "http://ha:8123", "HA_TOKEN": "t"}
    with pytest.raises(ConfigError):
        Settings.from_env(base)
    Settings.from_env({**base, "APP_PASSWORD": "123456"})
    Settings.from_env({**base, "AUTH_DISABLED": "true"})


@pytest.mark.parametrize(
    "env",
    [
        {"MODE": "cloud"},
        {"MODE": "homeassistant", "HA_URL": "ha:8123", "HA_TOKEN": "t", "AUTH_DISABLED": "1"},
        {"MODE": "homeassistant", "HA_URL": "http://ha", "AUTH_DISABLED": "1"},
        {"MODE": "demo", "AUTH_DISABLED": "1", "HA_VACUUM_ENTITY": "sensor.x"},
    ],
)
def test_config_rejects_invalid(env):
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_ws_url_and_repr_hides_secrets():
    s = Settings.from_env({"HA_URL": "https://ha.example/", "HA_TOKEN": "tok-xyz", "APP_PASSWORD": "abcdef"})
    assert s.ha_ws_url == "wss://ha.example/api/websocket"
    assert "tok-xyz" not in repr(s) and "abcdef" not in repr(s)


def test_every_error_translation_is_latvian():
    for code in known_codes():
        err = translate_error(code)
        assert err is not None
        for text in (err.title, err.explanation, err.action):
            assert text.strip() and text[0].isupper()
        assert LATVIAN_LETTERS.search(err.title + err.explanation + err.action), code


def test_no_error_codes():
    assert translate_error(0) is None and translate_error(100) is None and translate_error(None) is None


def test_unknown_error_keeps_number():
    err = translate_error(77777, "Something")
    assert "77777" in err.title and err.original == "Something"


def test_redaction():
    data = {
        "ha_token": "abc123456",
        "nested": [{"password": "x1234"}, {"url": "http://h/?access_token=zzz111"}],
        "note": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk",
        "email": "someone@example.com",
        "text": "contact someone@example.com",
        "free": "my secret is hunter22",
    }
    out = redact(data, extra_secrets=("hunter22",))
    flat = str(out)
    for secret in ("abc123456", "x1234", "zzz111", "eyJhbGci", "someone@example.com", "hunter22"):
        assert secret not in flat
    assert out["ha_token"] == REDACTED


def test_log_filter_redacts():
    record = logging.LogRecord("x", logging.INFO, "f", 1, "token is %s", ("tok-secret-1",), None)
    RedactingFilter(("tok-secret-1",)).filter(record)
    assert "tok-secret-1" not in record.getMessage()
    assert "REDACTED" in redact_text("Authorization: Bearer abc.def")


def test_auth_tokens(tmp_path):
    secret = load_secret("", tmp_path)
    assert load_secret("", tmp_path) == secret  # persisted
    assert (tmp_path / "secret_key").stat().st_mode & 0o077 == 0
    auth = Authenticator("parole123", secret, session_days=1)
    assert auth.verify_password("parole123") and not auth.verify_password("parole124")
    token = auth.issue()
    assert auth.check(token)
    assert not auth.check(token + "x") and not auth.check("1.2.3") and not auth.check(None)
    # changing the password invalidates old sessions
    assert not Authenticator("cita-parole", secret).check(token)
    expired = Authenticator("parole123", secret, session_days=-1)
    assert not expired.check(expired.issue())


def test_rate_limiter():
    limiter = LoginRateLimiter(max_failures=2, window=60)
    limiter.failed("a")
    assert not limiter.blocked("a")
    limiter.failed("a")
    assert limiter.blocked("a") and not limiter.blocked("b")
    limiter.reset("a")
    assert not limiter.blocked("a")


def test_storage_roundtrip():
    s = Storage(":memory:")
    s.set_setting("k", {"a": 1})
    assert s.get_setting("k") == {"a": 1} and s.get_setting("missing", 5) == 5
    sid = s.open_session("rooms", ["Virtuve"], "app")
    assert s.open_session_id() == sid
    s.close_session(sid, "finished", 3.0, 4.0)
    assert s.open_session_id() is None
    s.add_event("info", "x", "y")
    s.clear_history()
    assert s.sessions() == [] and s.events() == []


async def test_demo_adapter_is_marked_and_works():
    adapter = DemoAdapter(step_delay=0.01)
    await adapter.start()
    try:
        assert adapter.snapshot.demo is True
        assert "DEMO" in adapter.snapshot.model
        await adapter.send(CommandRequest(CommandName.START))
        assert adapter.snapshot.activity == Activity.CLEANING
        await asyncio.sleep(0.2)
        assert adapter.snapshot.activity == Activity.DOCKED
        render = render_map(await adapter.get_map_svg(), hide_carpet=False)
        assert render.carpet_found is True
    finally:
        await adapter.stop()
