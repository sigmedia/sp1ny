"""The keyboard shortcuts of the application: every key is defined here, and only here

The code only refers to an action by its name (see `shortcut`). An empty string means no shortcut.
"""

from __future__ import annotations

from pyqtgraph.Qt import QtGui

SHORTCUTS: dict[str, str] = {
    # File
    "open_file": "Ctrl+O",
    "quit": "Ctrl+Q",
    # Transport
    "play_pause": "Space",
    "stop": "Esc",
    "go_to_start": "Home",
    "go_to_end": "End",
    "rewind": "Left",
    "forward": "Right",
    "loop": "L",
    "speed_down": "[",
    "speed_up": "]",
    "mute": "M",
    # Annotations
    "delete_annotation": "Delete",
}


def shortcut(action: str) -> QtGui.QKeySequence:
    """Give the keyboard shortcut of an action

    Parameters
    ----------
    action : str
        The name of the action (a key of `SHORTCUTS`)

    Returns
    -------
    QtGui.QKeySequence
        The shortcut (empty if the action has none)
    """
    return QtGui.QKeySequence(SHORTCUTS[action])
