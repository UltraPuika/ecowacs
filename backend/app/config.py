"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Raised when the configuration is invalid."""


MODES = ("ecovacs", "homeassistant", "demo")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float(value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError as err:
        raise ConfigError(f"Invalid number: {value!r}") from err


@dataclass(frozen=True)
class Settings:
    """Application settings."""

    mode: str = "ecovacs"  # "ecovacs", "homeassistant" or "demo"
    ecovacs_username: str = field(default="", repr=False)
    ecovacs_password: str = field(default="", repr=False)
    ecovacs_country: str = "LV"
    ecovacs_device: str = ""
    ha_url: str = ""
    ha_token: str = field(default="", repr=False)
    ha_vacuum_entity: str = ""
    app_password: str = field(default="", repr=False)
    auth_disabled: bool = False
    secret_key: str = field(default="", repr=False)
    data_dir: Path = Path("/data")
    cors_origins: tuple[str, ...] = ()
    command_timeout: float = 15.0
    verify_timeout: float = 25.0
    dedupe_window: float = 4.0
    stale_after: float = 900.0
    session_days: float = 180.0
    secure_cookies: bool = False

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        """Create settings from environment variables."""
        env = dict(os.environ if env is None else env)
        mode = env.get("MODE", "ecovacs").strip().lower()
        if mode not in MODES:
            raise ConfigError("MODE must be 'ecovacs', 'homeassistant' or 'demo'")

        settings = cls(
            mode=mode,
            ecovacs_username=env.get("ECOVACS_USERNAME", "").strip(),
            ecovacs_password=env.get("ECOVACS_PASSWORD", ""),
            ecovacs_country=env.get("ECOVACS_COUNTRY", "LV").strip().upper(),
            ecovacs_device=env.get("ECOVACS_DEVICE", "").strip(),
            ha_url=env.get("HA_URL", "").strip().rstrip("/"),
            ha_token=env.get("HA_TOKEN", "").strip(),
            ha_vacuum_entity=env.get("HA_VACUUM_ENTITY", "").strip(),
            app_password=env.get("APP_PASSWORD", ""),
            auth_disabled=_bool(env.get("AUTH_DISABLED")),
            secret_key=env.get("SECRET_KEY", "").strip(),
            data_dir=Path(env.get("DATA_DIR", "/data")),
            cors_origins=tuple(
                o.strip() for o in env.get("CORS_ORIGINS", "").split(",") if o.strip()
            ),
            command_timeout=_float(env.get("COMMAND_TIMEOUT"), 15.0),
            verify_timeout=_float(env.get("VERIFY_TIMEOUT"), 25.0),
            dedupe_window=_float(env.get("DEDUPE_WINDOW"), 4.0),
            stale_after=_float(env.get("STALE_AFTER"), 900.0),
            session_days=_float(env.get("SESSION_DAYS"), 180.0),
            secure_cookies=_bool(env.get("SECURE_COOKIES")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """Validate the combination of settings."""
        if self.mode == "ecovacs":
            if not self.ecovacs_username or not self.ecovacs_password:
                raise ConfigError(
                    "ECOVACS_USERNAME and ECOVACS_PASSWORD are required when MODE=ecovacs"
                )
            if len(self.ecovacs_country) != 2 or not self.ecovacs_country.isalpha():
                raise ConfigError("ECOVACS_COUNTRY must be a two-letter country code, e.g. LV")
        if self.mode == "homeassistant":
            if not self.ha_url.startswith(("http://", "https://")):
                raise ConfigError("HA_URL must start with http:// or https://")
            if not self.ha_token:
                raise ConfigError("HA_TOKEN is required when MODE=homeassistant")
        if self.ha_vacuum_entity and not self.ha_vacuum_entity.startswith("vacuum."):
            raise ConfigError("HA_VACUUM_ENTITY must look like vacuum.<name>")
        if not self.auth_disabled and len(self.app_password) < 6:
            raise ConfigError(
                "APP_PASSWORD (at least 6 characters) is required, "
                "or set AUTH_DISABLED=true explicitly"
            )

    @property
    def ha_ws_url(self) -> str:
        """Home Assistant WebSocket URL."""
        if self.ha_url.startswith("https://"):
            return "wss://" + self.ha_url[len("https://") :] + "/api/websocket"
        return "ws://" + self.ha_url[len("http://") :] + "/api/websocket"
