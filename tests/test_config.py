import copy
import pathlib

import pytest
import yaml

from conftest import EXAMPLES


@pytest.fixture
def settings(qapp, monkeypatch):
    """The themes and the shortcuts, restored after the test"""
    from spiny.gui import shortcuts, theme

    monkeypatch.setattr(theme, "THEMES", copy.deepcopy(theme.THEMES))
    monkeypatch.setattr(shortcuts, "SHORTCUTS", dict(shortcuts.SHORTCUTS))
    # NOTE: spiny.config imported the dictionary of the themes by name
    monkeypatch.setattr("spiny.config.THEMES", theme.THEMES)
    return theme, shortcuts


def write(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_example_lists_every_setting_with_its_default_value():
    from spiny.gui.shortcuts import SHORTCUTS
    from spiny.gui.theme import THEMES

    example = yaml.safe_load((EXAMPLES / "config.yaml").read_text(encoding="utf-8"))
    assert example == {"theme": "light", "shortcuts": SHORTCUTS, "themes": THEMES}


def test_valid_settings_are_applied(settings, tmp_path):
    from spiny.config import load_config

    theme, shortcuts = settings
    path = write(
        tmp_path,
        """
theme: dark
themes:
  dark:
    playhead: "#00ff00"
shortcuts:
  play_pause: P
  loop: Ctrl+Shift+L
  mute:
""",
    )
    assert load_config(path) == "dark"
    assert theme.THEMES["dark"]["playhead"] == "#00ff00"
    assert shortcuts.shortcut("play_pause").toString() == "P"
    assert shortcuts.shortcut("loop").toString() == "Ctrl+Shift+L"
    assert shortcuts.shortcut("mute").isEmpty()


def test_mistakes_are_reported_and_keep_the_defaults(settings, tmp_path, caplog):
    from spiny.config import load_config

    theme, shortcuts = settings
    defaults = copy.deepcopy(theme.THEMES), dict(shortcuts.SHORTCUTS)
    path = write(
        tmp_path,
        """
theme: neon
colour: red
themes:
  neon: {}
  dark:
    playhead: #00ff00
    waveform: not-a-colour
    no_such_colour: "#000000"
  light: 3
shortcuts:
  no_such_action: A
  loop: 3
  stop: Ctrl+NoSuchKey
""",
    )
    assert load_config(path) == "light"
    assert (theme.THEMES, shortcuts.SHORTCUTS) == defaults
    for expected in (
        '"neon"',
        '"colour"',
        '"playhead"',
        '"waveform"',
        '"no_such_colour"',
        '"no_such_action"',
        '"loop"',
        '"stop"',
    ):
        assert expected in caplog.text


@pytest.mark.parametrize("text", ["{not yaml", "- a list", "theme: dark\nthemes: 3\nshortcuts: [a]"])
def test_broken_files_do_not_prevent_starting(settings, tmp_path, caplog, text):
    from spiny.config import load_config

    assert load_config(write(tmp_path, text)) in ("light", "dark")
    assert caplog.text


def test_missing_default_file_is_silent(settings, tmp_path, monkeypatch, caplog):
    import spiny.config

    monkeypatch.setattr(spiny.config, "default_config_path", lambda: tmp_path / "missing.yaml")
    assert spiny.config.load_config() == "light"
    assert not caplog.text


def test_two_actions_on_one_shortcut_are_reported(settings, caplog):
    _, shortcuts = settings
    shortcuts.configure_shortcuts({"mute": "L"})
    assert "several actions" in caplog.text and "mute" in caplog.text


def test_buttons_use_the_configured_shortcut(settings):
    from spiny.gui.icons import ToolBarButton

    _, shortcuts = settings
    shortcuts.configure_shortcuts({"loop": "Ctrl+L", "mute": ""})
    assert ToolBarButton("loop", "Loop", "loop")._shortcut.key().toString() == "Ctrl+L"
    no_shortcut = ToolBarButton("mute", "Mute", "mute")
    assert no_shortcut._shortcut.key().isEmpty() and no_shortcut.toolTip() == "Mute"
