"""The keyboard shortcuts and the wheel of the application: every binding is defined here, and only here

The code only refers to an action by its name (see `shortcut`). An empty string means no shortcut.
"""

from __future__ import annotations

import logging
from typing import Any

from pyqtgraph.Qt import QtGui, QtWidgets

logger = logging.getLogger(__name__)

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
    # View
    "zoom_in": "Ctrl+=",
    "zoom_out": "Ctrl+-",
    "zoom_fit": "Ctrl+0",
    "follow": "F",
    "switch_theme": "Ctrl+T",
    # Annotations
    "add_tier": "Ctrl+Shift+T",
    "remove_tier": "Ctrl+Shift+R",
    "add_annotation": "Ctrl+N",
    "toggle_tier_lock": "Ctrl+L",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Shift+Z",
    "delete_annotation": "Delete",
    "edit_label": "Insert",
}


#: The shortcuts of the application, whatever the configuration file changes in `SHORTCUTS`
DEFAULT_SHORTCUTS = dict(SHORTCUTS)

#: What the wheel does: two fingers on a trackpad are a wheel with two directions
WHEEL_ACTIONS: dict[str, str] = {
    "wheel_up_down": "zoom",
    "wheel_left_right": "pan",
    "shift_wheel_up_down": "pan",
    "shift_wheel_left_right": "pan",
}

#: What the wheel can do: "none" leaves the event to what is below (e.g. scrolling the tiers)
WHEEL_CHOICES = ("zoom", "pan", "none")


def configure_wheel(overrides: dict[str, Any]) -> None:
    """Change what the wheel does; a mistake is reported in the log and that binding keeps its value

    Parameters
    ----------
    overrides : dict
        The action of each gesture which changes
    """
    for gesture, action in overrides.items():
        if gesture not in WHEEL_ACTIONS:
            logger.warning(
                'Configuration: unknown gesture "%s", available ones are: %s', gesture, ", ".join(WHEEL_ACTIONS)
            )
        elif action not in WHEEL_CHOICES:
            logger.warning('Configuration: invalid action for "%s": %s (%s)', gesture, action, ", ".join(WHEEL_CHOICES))
        else:
            WHEEL_ACTIONS[gesture] = action


def wheel_action(horizontal: bool, shift: bool) -> str:
    """Give what a turn of the wheel does

    Parameters
    ----------
    horizontal : bool
        True if the movement is left or right, False if it is up or down
    shift : bool
        True if the Shift key is pressed

    Returns
    -------
    str
        "zoom", "pan" or "none"
    """
    return WHEEL_ACTIONS[f"{'shift_' if shift else ''}wheel_{'left_right' if horizontal else 'up_down'}"]


def configure_shortcuts(overrides: dict[str, Any]) -> None:
    """Change shortcuts; a mistake is reported in the log and that shortcut keeps its value

    Parameters
    ----------
    overrides : dict
        The shortcuts to change, by action; an empty value removes the shortcut of the action
    """
    for action, value in overrides.items():
        if action not in SHORTCUTS:
            logger.warning(
                'Configuration: unknown action "%s", available actions are: %s', action, ", ".join(SHORTCUTS)
            )
        elif not value:
            SHORTCUTS[action] = ""
        elif not isinstance(value, str) or not QtGui.QKeySequence(value).toString():
            logger.warning('Configuration: invalid shortcut for "%s": %s', action, value)
        else:
            SHORTCUTS[action] = value

    for key, actions in duplicated_keys(SHORTCUTS).items():
        logger.warning('Configuration: the shortcut "%s" is used by several actions: %s', key, ", ".join(actions))


def duplicated_keys(shortcuts: dict[str, str]) -> dict[str, list[str]]:
    """Find the shortcuts given to several actions: Qt triggers neither of them

    Parameters
    ----------
    shortcuts : dict
        The shortcut of each action

    Returns
    -------
    dict
        The actions of each shortcut used more than once
    """
    actions_by_key: dict[str, list[str]] = {}
    for action, value in shortcuts.items():
        if value:
            actions_by_key.setdefault(QtGui.QKeySequence(value).toString(), []).append(action)
    return {key: actions for key, actions in actions_by_key.items() if len(actions) > 1}


def set_shortcuts(shortcuts: dict[str, str]) -> None:
    """Change the shortcuts of an application which is already running

    Parameters
    ----------
    shortcuts : dict
        The shortcut of each action
    """
    SHORTCUTS.update(shortcuts)
    for widget in QtWidgets.QApplication.allWidgets():
        if hasattr(widget, "applyShortcuts"):
            widget.applyShortcuts()


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
