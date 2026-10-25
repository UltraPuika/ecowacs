"""Removes secrets and personal data from diagnostics and logs."""

from __future__ import annotations

import logging
import re
from typing import Any

REDACTED = "**REDACTED**"
_SECRET_KEYS = re.compile(
    r"(token|password|passwd|secret|authorization|cookie|api[_-]?key|session|credential|email|username)",
    re.IGNORECASE,
)
_PATTERNS = [
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer " + REDACTED),
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), REDACTED),  # JWT
    (re.compile(r"(?i)(access_token|token|password|secret)=([^&\s\"']+)"), r"\1=" + REDACTED),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "**EMAIL**"),
]


def redact_text(text: str, extra_secrets: tuple[str, ...] = ()) -> str:
    """Redact secrets inside free text."""
    for secret in extra_secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, REDACTED)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact(value: Any, extra_secrets: tuple[str, ...] = ()) -> Any:
    """Recursively redact secret-looking keys and values."""
    if isinstance(value, dict):
        return {
            k: (REDACTED if isinstance(k, str) and _SECRET_KEYS.search(k) and v not in (None, "", False)
                else redact(v, extra_secrets))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v, extra_secrets) for v in value]
    if isinstance(value, str):
        return redact_text(value, extra_secrets)
    return value


class RedactingFilter(logging.Filter):
    """Logging filter that redacts known secrets from every record."""

    def __init__(self, secrets: tuple[str, ...]) -> None:
        super().__init__()
        self._secrets = secrets

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage(), self._secrets)
        record.args = ()
        return True
