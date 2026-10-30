"""One-time login for direct mode (no Home Assistant).

    docker compose run --rm backend python -m app.ecovacs_login

It asks for the Ecovacs account e-mail and password, handles Ecovacs'
one-time e-mail verification code if it is requested, and then saves only
Ecovacs' access token (never the password) in the data volume.

It makes ONE login attempt. A wrong password or country is reported and not
retried, so the account is never hammered. A mistyped e-mail code may be
re-entered up to three times.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import aiohttp
from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.exceptions import (
    DeebotError,
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
    InvalidVerificationCodeError,
)
from deebot_client.util import md5

from .ecovacs_session import StoredSession, load_session, new_device_id, save_session, valid_country

MAX_CODE_ATTEMPTS = 3


async def login(
    *,
    data_dir: Path,
    country: str,
    email: str,
    password: str,
    ask_code: Callable[[], str],
    say: Callable[[str], None] = print,
    http_session: aiohttp.ClientSession | None = None,
    authenticator_factory: Callable[[aiohttp.ClientSession, str], Authenticator] | None = None,
) -> int:
    """Run the login. Returns a process exit status (0 = success)."""
    country = valid_country(country)
    existing = load_session(data_dir)
    # Reuse the device ID: a code that was already verified stays valid for it.
    device_id = existing.device_id if existing else new_device_id()

    own_session = http_session is None
    http = http_session or aiohttp.ClientSession()

    def default_factory(session: aiohttp.ClientSession, dev_id: str) -> Authenticator:
        return Authenticator(
            create_rest_config(session, device_id=dev_id, alpha_2_country=country),
            email,
            md5(password),
        )

    authenticator = (authenticator_factory or default_factory)(http, device_id)
    try:
        try:
            await authenticator.authenticate()
        except DeviceVerificationRequiredError:
            say("Ecovacs wants to verify this installation. A code was sent to your e-mail.")
            try:
                await authenticator.request_device_verification_code()
            except DeebotError as err:
                say(f"Could not request the verification code: {err}")
                return 3
            for attempt in range(1, MAX_CODE_ATTEMPTS + 1):
                code = ask_code().strip()
                try:
                    await authenticator.verify_device(code)
                    break
                except InvalidVerificationCodeError:
                    say(f"That code was not accepted (attempt {attempt} of {MAX_CODE_ATTEMPTS}).")
            else:
                say("Too many wrong codes. Run the command again to get a new code.")
                return 3
        except InvalidAuthenticationError:
            say(
                "Login was refused: wrong e-mail, password or country.\n"
                "Check them (the country must be the one the Ecovacs account was created in), "
                "then run the command again. It is not retried automatically."
            )
            return 2

        account = authenticator.account_credentials
        if account is None:
            say("Login finished but Ecovacs returned no reusable token. Nothing was saved.")
            return 4
        save_session(
            data_dir,
            StoredSession(device_id, country, user_id=account.user_id, access_token=account.access_token),
        )
        say("Login saved. The password was NOT stored.")
        await _list_robots(authenticator, say)
        return 0
    except DeebotError as err:
        say(f"Could not reach Ecovacs: {err}")
        return 5
    finally:
        await authenticator.teardown()
        if own_session:
            await http.close()


async def _list_robots(authenticator: Authenticator, say: Callable[[str], None]) -> None:
    try:
        devices = await ApiClient(authenticator).get_devices()
    except DeebotError as err:
        say(f"Saved, but the robot list could not be read now: {err}")
        return
    found: list[tuple[str, dict[str, Any], bool]] = [
        ("supported", info.api, True) for info in devices.mqtt
    ]
    found += [("older protocol, NOT supported", info, False) for info in devices.xmpp]
    found += [("unknown model, NOT supported", info, False) for info in devices.not_supported]
    if not found:
        say("The account has no robots.")
        return
    say("Robots on this account:")
    for label, info, _ok in found:
        name = info.get("nick") or info.get("name") or "?"
        say(f"  - {name} | {info.get('deviceName', '?')} | class {info.get('class', '?')} | {label}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--country", default=os.environ.get("ECOVACS_COUNTRY", ""),
                        help="two-letter country of the Ecovacs account, e.g. LV (or set ECOVACS_COUNTRY)")
    parser.add_argument("--email", default=os.environ.get("ECOVACS_EMAIL", ""))
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("DATA_DIR", "/data")))
    args = parser.parse_args(argv)

    if not sys.stdin.isatty() and not os.environ.get("ECOVACS_PASSWORD"):
        print("This command asks questions: run it in an interactive terminal "
              "(docker compose run --rm backend python -m app.ecovacs_login).")
        return 1
    try:
        country = valid_country(args.country or input("Country of the Ecovacs account (two letters, e.g. LV): "))
    except ValueError as err:
        print(err)
        return 1
    email = args.email or input("Ecovacs e-mail: ").strip()
    password = os.environ.get("ECOVACS_PASSWORD") or getpass.getpass("Ecovacs password (not shown, not stored): ")
    if not email or not password:
        print("E-mail and password are required.")
        return 1
    run: Awaitable[int] = login(
        data_dir=args.data_dir, country=country, email=email, password=password,
        ask_code=lambda: input("Verification code from the e-mail: "),
    )
    return asyncio.run(run)  # type: ignore[arg-type]


if __name__ == "__main__":
    sys.exit(main())
