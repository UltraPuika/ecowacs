"""Robot adapters."""

from ..config import Settings
from .base import AdapterError, NotConnectedError, RobotAdapter, UnsupportedError


def create_adapter(settings: Settings) -> RobotAdapter:
    """Create the adapter selected by ``MODE``."""
    if settings.mode == "demo":
        from .demo import DemoAdapter

        return DemoAdapter()
    if settings.mode == "direct":
        try:
            from .direct import DirectAdapter
        except ImportError as err:  # deebot-client needs Python 3.14
            raise RuntimeError(
                "MODE=direct needs the deebot-client library, which requires Python 3.14 or newer "
                "(the Docker image has it). See docs/DIRECT_MODE.md."
            ) from err
        return DirectAdapter(settings)
    from .homeassistant import HomeAssistantAdapter

    return HomeAssistantAdapter(settings)


__all__ = ["AdapterError", "NotConnectedError", "RobotAdapter", "UnsupportedError", "create_adapter"]
