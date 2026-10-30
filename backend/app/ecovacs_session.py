"""The saved Ecovacs login session for direct mode.

Only a device ID, the country and Ecovacs' own access token are stored. The
account password is never written to disk. The token lets the app renew its
connection without the password, so the one-time login (``python -m
app.ecovacs_login``) is not repeated.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import string
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SESSION_FILE = "ecovacs_session.json"
_COUNTRY = re.compile(r"^[A-Za-z]{2}$")


@dataclass(frozen=True)
class StoredSession:
    """What survives between runs."""

    device_id: str
    country: str
    user_id: str = ""
    access_token: str = field(default="", repr=False)

    @property
    def has_login(self) -> bool:
        """True when a login has been completed and saved."""
        return bool(self.user_id and self.access_token)


def new_device_id() -> str:
    """A random client ID. Ecovacs ties the e-mail verification to it."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


def valid_country(country: str) -> str:
    """Return the upper-case two-letter country code or raise ValueError."""
    if not isinstance(country, str) or not _COUNTRY.match(country.strip()):
        raise ValueError("Country must be a two-letter code such as LV")
    return country.strip().upper()


def session_path(data_dir: Path) -> Path:
    return data_dir / SESSION_FILE


def load_session(data_dir: Path) -> StoredSession | None:
    """Read the saved session, or None if there is none or it is unreadable."""
    try:
        raw = json.loads(session_path(data_dir).read_text(encoding="utf-8"))
        return StoredSession(
            device_id=str(raw["device_id"]),
            country=valid_country(raw["country"]),
            user_id=str(raw.get("user_id", "")),
            access_token=str(raw.get("access_token", "")),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_session(data_dir: Path, session: StoredSession) -> None:
    """Write the session atomically with owner-only permissions."""
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "device_id": session.device_id,
            "country": session.country,
            "user_id": session.user_id,
            "access_token": session.access_token,
        }
    )
    fd, tmp = tempfile.mkstemp(dir=data_dir, prefix=".session-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.chmod(tmp, 0o600)
        os.replace(tmp, session_path(data_dir))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
