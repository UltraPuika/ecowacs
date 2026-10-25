"""Local password authentication with signed session cookies."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

COOKIE_NAME = "deebot_session"


def load_secret(configured: str, data_dir: Path) -> bytes:
    """Use SECRET_KEY if set, else a random key persisted in the data directory."""
    if configured:
        return configured.encode()
    path = data_dir / "secret_key"
    if path.exists():
        return path.read_bytes().strip()
    data_dir.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(key)
    return key


class Authenticator:
    """Verifies the app password and issues/validates session tokens."""

    def __init__(self, password: str, secret: bytes, session_days: float = 180.0) -> None:
        self._salt = secrets.token_bytes(16)
        self._hash = self._derive(password) if password else b""
        # Sessions are bound to the password, so changing it logs everyone out.
        self._key = hmac.new(secret, hashlib.sha256(password.encode()).digest(), "sha256").digest()
        self._ttl = int(session_days * 86400)

    def _derive(self, password: str) -> bytes:
        return hashlib.scrypt(password.encode(), salt=self._salt, n=2**14, r=8, p=1, dklen=32)

    def verify_password(self, candidate: str) -> bool:
        """Constant-time password check."""
        if not self._hash or not isinstance(candidate, str) or len(candidate) > 256:
            return False
        return hmac.compare_digest(self._derive(candidate), self._hash)

    def issue(self) -> str:
        """Create a signed session token."""
        payload = f"{int(time.time()) + self._ttl}.{secrets.token_urlsafe(12)}"
        return f"{payload}.{self._sign(payload)}"

    def check(self, token: str | None) -> bool:
        """Validate a session token."""
        if not token or token.count(".") != 2:
            return False
        payload, _, signature = token.rpartition(".")
        if not hmac.compare_digest(self._sign(payload), signature):
            return False
        try:
            return int(payload.split(".", 1)[0]) > time.time()
        except ValueError:
            return False

    def _sign(self, payload: str) -> str:
        digest = hmac.new(self._key, payload.encode(), "sha256").digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    @property
    def max_age(self) -> int:
        """Cookie lifetime in seconds."""
        return self._ttl


class LoginRateLimiter:
    """Allows a few failed logins per client, then blocks for a while."""

    def __init__(self, max_failures: int = 5, window: float = 300.0) -> None:
        self._max = max_failures
        self._window = window
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, client: str, now: float) -> deque[float]:
        q = self._failures[client]
        while q and now - q[0] > self._window:
            q.popleft()
        return q

    def blocked(self, client: str) -> bool:
        return len(self._prune(client, time.monotonic())) >= self._max

    def failed(self, client: str) -> None:
        self._prune(client, time.monotonic()).append(time.monotonic())

    def reset(self, client: str) -> None:
        self._failures.pop(client, None)
