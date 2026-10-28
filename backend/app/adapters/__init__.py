"""Robot adapters."""

from ..config import Settings
from .base import AdapterError, NotConnectedError, RobotAdapter, UnsupportedError


def create_adapter(settings: Settings) -> RobotAdapter:
    """Create the adapter selected by ``MODE``."""
    if settings.mode == "demo":
        from .demo import DemoAdapter

        return DemoAdapter()
    if settings.mode == "ecovacs":
        from .ecovacs import EcovacsAdapter

        return EcovacsAdapter(settings)
    from .homeassistant import HomeAssistantAdapter

    return HomeAssistantAdapter(settings)


__all__ = ["AdapterError", "NotConnectedError", "RobotAdapter", "UnsupportedError", "create_adapter"]
