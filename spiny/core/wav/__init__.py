from .player import player as player
from .control import PlayerControllerWidget
from .control import get_controller

__all__ = ["player", "PlayerControllerWidget", "get_controller"]


def __getattr__(name):
    # Backward compatibility: "from spiny.core.wav import controller" creates the controller lazily
    if name == "controller":
        return get_controller()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
