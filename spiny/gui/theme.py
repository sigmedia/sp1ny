"""The look of the application: every colour and style sheet is defined here, for each theme

Widgets and graphics items only ask for a colour by name (see `color`). Those which cannot simply follow the palette
define an `applyTheme` method, which `apply_theme` calls to switch the theme of an application already running.
"""

from __future__ import annotations

import logging
from string import Template
from typing import Any

import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets

logger = logging.getLogger(__name__)

# NOTE: a colour is anything QColor understands; the transparent ones are written #AARRGGBB
THEMES: dict[str, dict[str, str]] = {
    "light": {
        # Palette of the widgets
        "window": "#efefef",
        "window_text": "#000000",
        "base": "#ffffff",
        "alternate_base": "#f7f7f7",
        "text": "#000000",
        "button": "#efefef",
        "button_text": "#000000",
        "bright_text": "#ff0000",
        "link": "#0000ff",
        "highlight": "#308cc6",
        "highlighted_text": "#ffffff",
        "tooltip_background": "#2a82da",
        "tooltip_text": "#ffffff",
        # Plots
        "plot_background": "#ffffff",
        "plot_foreground": "#000000",
        "waveform": "#000000",
        "playhead": "#e5484d",
        "selection": "#320000ff",
        "selection_hover": "#32ff0000",
        # Annotations
        "tier_background": "#19000000",
        "annotation": "#f7f7f7",
        "annotation_text": "#000000",
        "annotation_border": "#a8a84c",
        "annotation_hover": "#640000ff",
        "annotation_selected": "#32ff0000",
        "hidden_tier": "#eaa799",
        "hidden_tier_text": "#000000",
        "ipa_hover": "#867d7d",
        "ipa_hover_text": "#ffffff",
        # Toolbars
        "accent": "#2a78d6",
        "accent_text": "#ffffff",
        "play": "#2fa66a",
        "button_hover": "#327f7f7f",
        "button_pressed": "#5a7f7f7f",
        "slider_groove": "#5a7f7f7f",
        "display_background": "#17181a",
        "display_text": "#7fe3a8",
        "display_dim_text": "#7c8088",
    },
    "dark": {
        "window": "#353535",
        "window_text": "#ffffff",
        "base": "#191919",
        "alternate_base": "#353535",
        "text": "#ffffff",
        "button": "#353535",
        "button_text": "#ffffff",
        "bright_text": "#ff0000",
        "link": "#2a82da",
        "highlight": "#2a82da",
        "highlighted_text": "#000000",
        "tooltip_background": "#2a82da",
        "tooltip_text": "#ffffff",
        "plot_background": "#191919",
        "plot_foreground": "#d0d0d0",
        "waveform": "#ffffff",
        "playhead": "#e5484d",
        "selection": "#320000ff",
        "selection_hover": "#32ff0000",
        "tier_background": "#19000000",
        "annotation": "#353535",
        "annotation_text": "#ffffff",
        "annotation_border": "#c8c864",
        "annotation_hover": "#640000ff",
        "annotation_selected": "#32ff0000",
        "hidden_tier": "#eaa799",
        "hidden_tier_text": "#000000",
        "ipa_hover": "#867d7d",
        "ipa_hover_text": "#ffffff",
        "accent": "#2a78d6",
        "accent_text": "#ffffff",
        "play": "#2fa66a",
        "button_hover": "#327f7f7f",
        "button_pressed": "#5a7f7f7f",
        "slider_groove": "#5a7f7f7f",
        "display_background": "#17181a",
        "display_text": "#7fe3a8",
        "display_dim_text": "#7c8088",
    },
}

_PALETTE_ROLES = {
    QtGui.QPalette.ColorRole.Window: "window",
    QtGui.QPalette.ColorRole.WindowText: "window_text",
    QtGui.QPalette.ColorRole.Base: "base",
    QtGui.QPalette.ColorRole.AlternateBase: "alternate_base",
    QtGui.QPalette.ColorRole.Text: "text",
    QtGui.QPalette.ColorRole.Button: "button",
    QtGui.QPalette.ColorRole.ButtonText: "button_text",
    QtGui.QPalette.ColorRole.BrightText: "bright_text",
    QtGui.QPalette.ColorRole.Link: "link",
    QtGui.QPalette.ColorRole.Highlight: "highlight",
    QtGui.QPalette.ColorRole.HighlightedText: "highlighted_text",
    QtGui.QPalette.ColorRole.ToolTipBase: "tooltip_background",
    QtGui.QPalette.ColorRole.ToolTipText: "tooltip_text",
}

_STYLE_SHEET = Template("""
    QToolTip { color: $tooltip_text; background-color: $tooltip_background; border: 1px solid $tooltip_text; }
    QLabelClickable:hover { background-color: $ipa_hover; color: $ipa_hover_text; }

    ToolBarButton { border: none; border-radius: 6px; padding: 5px; }
    ToolBarButton:hover { background: $button_hover; }
    ToolBarButton:pressed { background: $button_pressed; }
    ToolBarButton:checked { background: $accent; }
    ToolBarButton:disabled { background: transparent; }

    QLabel#time, QLabel#duration, QLabel#speed {
        background: $display_background; border-radius: 6px; padding: 4px 10px;
    }
    QLabel#time, QLabel#speed { color: $display_text; }
    QLabel#duration { color: $display_dim_text; }

    OutputWidget QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: $slider_groove; }
    OutputWidget QSlider::sub-page:horizontal { border-radius: 2px; background: $accent; }
    OutputWidget QSlider::handle:horizontal {
        width: 12px; margin: -4px 0; border-radius: 6px; background: $button_text;
    }
""")

_current_theme = "light"


def color(name: str) -> QtGui.QColor:
    """Give a colour of the current theme

    Parameters
    ----------
    name : str
        The name of the colour (a key of `THEMES`)

    Returns
    -------
    QtGui.QColor
        The colour
    """
    return QtGui.QColor(THEMES[_current_theme][name])


def current_theme() -> str:
    """Give the name of the current theme

    Returns
    -------
    str
        A key of `THEMES`
    """
    return _current_theme


def _styleSheet() -> str:
    """Fill the style sheet of the application with the colours of the current theme

    Returns
    -------
    str
        The style sheet
    """

    def css(name: str) -> str:
        c = color(name)
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()})"

    return _STYLE_SHEET.substitute({name: css(name) for name in THEMES[_current_theme]})


def configure_themes(overrides: dict[str, Any]) -> None:
    """Change colours of the themes; a mistake is reported in the log and that colour keeps its value

    Parameters
    ----------
    overrides : dict
        The colours to change, by theme: {theme name: {colour name: colour}}
    """
    for theme_name, colors in overrides.items():
        if theme_name not in THEMES:
            logger.warning('Configuration: unknown theme "%s", available themes are: %s', theme_name, ", ".join(THEMES))
            continue
        if not isinstance(colors, dict):
            logger.warning('Configuration: the colours of the theme "%s" must be a mapping', theme_name)
            continue
        for name, value in colors.items():
            if name not in THEMES[theme_name]:
                logger.warning('Configuration: unknown colour "%s" in the theme "%s"', name, theme_name)
            elif not isinstance(value, str) or not QtGui.QColor(value).isValid():
                # NOTE: an unquoted #rrggbb is a comment in YAML, hence a missing value here
                logger.warning('Configuration: invalid colour for "%s" (quote it: "#rrggbb"): %s', name, value)
            else:
                THEMES[theme_name][name] = value


def apply_theme(name: str) -> None:
    """Make a theme the current one, for the application and for everything already on the screen

    Parameters
    ----------
    name : str
        The name of the theme (a key of `THEMES`)
    """
    global _current_theme
    _current_theme = name

    app = QtWidgets.QApplication.instance()
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    for role, color_name in _PALETTE_ROLES.items():
        palette.setColor(role, color(color_name))
    app.setPalette(palette)
    app.setStyleSheet(_styleSheet())

    # What is created from now on
    pg.setConfigOption("background", color("plot_background"))
    pg.setConfigOption("foreground", color("plot_foreground"))

    # What already exists (also the plots of the other plugins: they are hidden, not destroyed)
    for widget in app.allWidgets():
        if isinstance(widget, pg.GraphicsView):
            widget.setBackground(color("plot_background"))
            for item in widget.scene().items():
                if isinstance(item, pg.AxisItem):
                    item.setPen()  # NOTE: without argument, an axis follows the "foreground" option
                    item.setTextPen()
                elif hasattr(item, "applyTheme"):
                    item.applyTheme()
        if hasattr(widget, "applyTheme"):
            widget.applyTheme()


def toggle_theme() -> None:
    """Switch to the next theme"""
    names = list(THEMES)
    apply_theme(names[(names.index(_current_theme) + 1) % len(names)])
