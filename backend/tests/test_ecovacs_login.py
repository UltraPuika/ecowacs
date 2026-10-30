"""The one-time login helper: one attempt, e-mail code handling, nothing sensitive stored."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("deebot_client")

from deebot_client.exceptions import (  # noqa: E402
    DeebotError,
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
    InvalidVerificationCodeError,
)
from deebot_client.models import AccountCredentials  # noqa: E402

import app.ecovacs_login as login_module  # noqa: E402
from app.ecovacs_login import login  # noqa: E402
from app.ecovacs_session import SESSION_FILE, StoredSession, load_session, save_session  # noqa: E402

PASSWORD = "my-ecovacs-password-123"
EMAIL = "someone@example.com"


class FakeAuth:
    def __init__(self, *, needs_code=False, bad_credentials=False, good_code="123456", token=True):
        self.needs_code, self.bad_credentials, self.good_code = needs_code, bad_credentials, good_code
        self.account_credentials = AccountCredentials("access-tok", "user-1") if token else None
        self.authenticate_calls = 0
        self.codes_requested = 0
        self.codes_tried: list[str] = []
        self.torn_down = False

    async def authenticate(self):
        self.authenticate_calls += 1
        if self.bad_credentials:
            raise InvalidAuthenticationError("no")
        if self.needs_code:
            raise DeviceVerificationRequiredError("verify")

    async def request_device_verification_code(self):
        self.codes_requested += 1

    async def verify_device(self, code):
        self.codes_tried.append(code)
        if code != self.good_code:
            raise InvalidVerificationCodeError("bad code")

    async def teardown(self):
        self.torn_down = True


class FakeApi:
    def __init__(self, _auth):
        pass

    async def get_devices(self):
        info = SimpleNamespace(api={"nick": "Robis", "deviceName": "DEEBOT X9 PRO OMNI", "class": "ilt3k8", "did": "SECRET-DID"})
        return SimpleNamespace(mqtt=[info], xmpp=[], not_supported=[{"nick": "Old", "class": "zzz"}])


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    monkeypatch.setattr(login_module, "ApiClient", FakeApi)


async def run(tmp_path, auth, codes=(), **kw):
    said: list[str] = []
    answers = iter(codes)
    status = await login(
        data_dir=tmp_path, country="lv", email=EMAIL, password=PASSWORD,
        ask_code=lambda: next(answers), say=said.append,
        authenticator_factory=lambda _http, _dev: auth, **kw,
    )
    return status, "\n".join(said)


async def test_success_saves_token_but_never_the_password_or_email(tmp_path):
    auth = FakeAuth()
    status, out = await run(tmp_path, auth)
    assert status == 0 and auth.authenticate_calls == 1 and auth.torn_down
    saved = load_session(tmp_path)
    assert saved and saved.has_login and saved.country == "LV" and saved.access_token == "access-tok"
    on_disk = (tmp_path / SESSION_FILE).read_text()
    assert PASSWORD not in on_disk and EMAIL not in on_disk
    assert PASSWORD not in out and "SECRET-DID" not in out
    assert "Robis" in out and "ilt3k8" in out and "NOT supported" in out


async def test_verification_code_flow(tmp_path):
    auth = FakeAuth(needs_code=True)
    status, out = await run(tmp_path, auth, codes=["000000", "123456"])
    assert status == 0 and auth.codes_requested == 1 and auth.codes_tried == ["000000", "123456"]
    assert auth.authenticate_calls == 1  # no second password login
    assert load_session(tmp_path).has_login


async def test_three_wrong_codes_stop_and_save_nothing(tmp_path):
    auth = FakeAuth(needs_code=True)
    status, out = await run(tmp_path, auth, codes=["1", "2", "3"])
    assert status == 3 and len(auth.codes_tried) == 3
    assert load_session(tmp_path) is None and "Too many wrong codes" in out


async def test_wrong_password_is_reported_once_and_not_retried(tmp_path):
    auth = FakeAuth(bad_credentials=True)
    status, out = await run(tmp_path, auth)
    assert status == 2 and auth.authenticate_calls == 1
    assert load_session(tmp_path) is None and "not retried" in out
    assert PASSWORD not in out


async def test_device_id_is_reused_so_a_verified_code_stays_valid(tmp_path):
    save_session(tmp_path, StoredSession("KEEP1234", "LV", "old", "old"))
    seen: list[str] = []

    def factory(_http, dev_id):
        seen.append(dev_id)
        return FakeAuth()

    await login(data_dir=tmp_path, country="LV", email=EMAIL, password=PASSWORD,
                ask_code=lambda: "", say=lambda _m: None, authenticator_factory=factory)
    assert seen == ["KEEP1234"] and load_session(tmp_path).device_id == "KEEP1234"


async def test_no_reusable_token_saves_nothing(tmp_path):
    status, out = await run(tmp_path, FakeAuth(token=False))
    assert status == 4 and load_session(tmp_path) is None


async def test_unreachable_ecovacs_is_reported(tmp_path):
    class Down(FakeAuth):
        async def authenticate(self):
            raise DeebotError("offline")

    status, out = await run(tmp_path, Down())
    assert status == 5 and "Could not reach Ecovacs" in out


async def test_invalid_country_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        await login(data_dir=tmp_path, country="Latvia", email=EMAIL, password=PASSWORD,
                    ask_code=lambda: "", say=lambda _m: None, authenticator_factory=lambda *_: FakeAuth())
    assert not (tmp_path / SESSION_FILE).exists()


def test_session_file_is_valid_json_with_only_expected_keys(tmp_path):
    save_session(tmp_path, StoredSession("A", "LV", "u", "t"))
    assert set(json.loads((tmp_path / SESSION_FILE).read_text())) == {"device_id", "country", "user_id", "access_token"}
