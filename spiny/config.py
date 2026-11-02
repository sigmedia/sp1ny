"""The configuration file of the user: the theme and the keyboard shortcuts

See examples/config.yaml for every setting and its default value. A mistake in the file is reported in the log and
that setting keeps its default: it must never prevent the application from starting.
"""

from __future__ import annotations

import logging
import os
import pathlib
from typing import Any

import yaml
from pyqtgraph.Qt import QtCore

from spiny.gui.shortcuts import configure_shortcuts
from spiny.gui.theme import THEMES, configure_themes

logger = logging.getLogger(__name__)


def default_config_path() -> pathlib.Path:
    """Give where the configuration file is looked for, when none is given on the command line

    Returns
    -------
    pathlib.Path
        spiny/config.yaml in the configuration directory of the user (~/.config on Linux)
    """
    config_directory = QtCore.QStandardPaths.writableLocation(
        QtCore.QStandardPaths.StandardLocation.GenericConfigLocation
    )
    return pathlib.Path(config_directory) / "spiny" / "config.yaml"


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    """Read a section of the configuration

    Parameters
    ----------
    config : dict
        The configuration
    name : str
        The name of the section

    Returns
    -------
    dict
        The section (empty if it is missing or not a mapping)
    """
    section = config.get(name) or {}
    if not isinstance(section, dict):
        logger.warning('Configuration: "%s" must be a mapping, it is ignored', name)
        return {}
    return section


def load_config(path: str | os.PathLike | None = None) -> str:
    """Read the configuration file and apply its shortcuts and its colours

    Parameters
    ----------
    path : str or pathlib.Path, optional
        The configuration file. (default: None, i.e. `default_config_path`, which does not have to exist)

    Returns
    -------
    str
        The name of the theme to start with
    """
    path = default_config_path() if path is None else pathlib.Path(path)
    if not path.is_file():
        return "light"

    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as ex:
        logger.warning('Cannot read the configuration file "%s": %s', path, ex)
        return "light"
    if not isinstance(config, dict):
        logger.warning('The configuration file "%s" must contain a mapping, it is ignored', path)
        return "light"

    for key in config.keys() - {"theme", "themes", "shortcuts"}:
        logger.warning('Configuration: unknown setting "%s"', key)

    configure_themes(_section(config, "themes"))
    configure_shortcuts(_section(config, "shortcuts"))

    theme_name = config.get("theme", "light")
    if theme_name not in THEMES:
        logger.warning('Configuration: unknown theme "%s", available themes are: %s', theme_name, ", ".join(THEMES))
        return "light"
    return theme_name
