"""Icons and buttons of the toolbars, drawn as vector shapes so that they look the same on every system"""

from __future__ import annotations

from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from spiny.gui import theme
from spiny.gui.shortcuts import shortcut


def _polygon(*points: tuple[float, float]) -> QtGui.QPainterPath:
    """Build a closed polygon

    Parameters
    ----------
    points : list(tuple(float, float))
        The corners, on a 24 × 24 grid

    Returns
    -------
    QtGui.QPainterPath
        The shape
    """
    path = QtGui.QPainterPath()
    path.addPolygon(QtGui.QPolygonF([QtCore.QPointF(*point) for point in points]))
    path.closeSubpath()
    return path


def _roundedRect(x: float, y: float, width: float, height: float, radius: float = 1.0) -> QtGui.QPainterPath:
    """Build a rounded rectangle

    Parameters
    ----------
    x, y, width, height : float
        The rectangle, on a 24 × 24 grid
    radius : float, optional
        The radius of the corners. (default: 1.0)

    Returns
    -------
    QtGui.QPainterPath
        The shape
    """
    path = QtGui.QPainterPath()
    path.addRoundedRect(x, y, width, height, radius, radius)
    return path


def _stroked(path: QtGui.QPainterPath, width: float = 2.0) -> QtGui.QPainterPath:
    """Turn a line into a shape which can be filled

    Parameters
    ----------
    path : QtGui.QPainterPath
        The line
    width : float, optional
        The thickness of the line. (default: 2.0)

    Returns
    -------
    QtGui.QPainterPath
        The shape
    """
    stroker = QtGui.QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
    return stroker.createStroke(path)


def _symbol(x: float, y: float, plus: bool) -> QtGui.QPainterPath:
    """Build a small plus or minus sign

    Parameters
    ----------
    x : float
        The centre of the sign
    y : float
        The centre of the sign
    plus : bool
        True for a plus sign, False for a minus sign

    Returns
    -------
    QtGui.QPainterPath
        The shape
    """
    bar = _roundedRect(x - 3.5, y - 1, 7, 2, 0.5)
    return bar + _roundedRect(x - 1, y - 3.5, 2, 7, 0.5) if plus else bar


def _shape(name: str) -> QtGui.QPainterPath:
    """Build the shape of an icon

    Parameters
    ----------
    name : str
        The name of the icon

    Returns
    -------
    QtGui.QPainterPath
        The shape, on a 24 × 24 grid
    """
    if name in ("add_tier", "remove_tier"):
        shape = _roundedRect(3, 5, 18, 4) + _roundedRect(3, 15, 10, 4)
        return shape + _symbol(18, 17, name == "add_tier")
    if name in ("add_annotation", "remove_annotation"):
        shape = _roundedRect(3, 4, 2, 16, 0.5) + _roundedRect(13, 4, 2, 16, 0.5) + _roundedRect(5, 11, 8, 2, 0.5)
        return shape + _symbol(19, 12, name == "add_annotation")
    if name in ("undo", "redo"):
        arc = QtGui.QPainterPath(QtCore.QPointF(7, 9))
        arc.lineTo(14, 9)
        arc.cubicTo(21, 9, 21, 19, 14, 19)
        arc.lineTo(9, 19)
        shape = _stroked(arc) + _polygon((8.5, 4.5), (3, 9), (8.5, 13.5))
        return shape if name == "undo" else QtGui.QTransform(-1, 0, 0, 1, 24, 0).map(shape)
    if name == "lock":
        shackle = QtGui.QPainterPath(QtCore.QPointF(8, 11))
        shackle.lineTo(8, 8)
        shackle.arcTo(8, 4, 8, 8, 180, -180)
        shackle.lineTo(16, 11)
        return _roundedRect(5, 11, 14, 9, 1.5) + _stroked(shackle)
    if name == "rewind":
        return _polygon((11.5, 5), (3, 12), (11.5, 19)) + _polygon((21, 5), (12.5, 12), (21, 19))
    if name == "forward":
        return _polygon((12.5, 5), (21, 12), (12.5, 19)) + _polygon((3, 5), (11.5, 12), (3, 19))
    if name == "end":
        return _roundedRect(16.5, 5, 2.5, 14) + _polygon((4.5, 5), (14.5, 12), (4.5, 19))
    if name == "minus":
        return _roundedRect(5, 10.5, 14, 3, 1.5)
    if name == "plus":
        return _roundedRect(5, 10.5, 14, 3, 1.5) + _roundedRect(10.5, 5, 3, 14, 1.5)
    if name == "mute":
        cross = QtGui.QPainterPath(QtCore.QPointF(15.5, 9))
        cross.lineTo(20.5, 15)
        cross.moveTo(20.5, 9)
        cross.lineTo(15.5, 15)
        return _polygon((3.5, 9), (7.5, 9), (12.5, 5), (12.5, 19), (7.5, 15), (3.5, 15)) + _stroked(cross)
    if name in ("zoom_in", "zoom_out"):
        lens = QtGui.QPainterPath()
        lens.addEllipse(QtCore.QPointF(10, 10), 6.5, 6.5)
        handle = QtGui.QPainterPath(QtCore.QPointF(15, 15))
        handle.lineTo(20.5, 20.5)
        shape = _stroked(lens) + _stroked(handle, 2.5) + _roundedRect(7, 9.2, 6, 1.6, 0.5)
        return shape + _roundedRect(9.2, 7, 1.6, 6, 0.5) if name == "zoom_in" else shape
    if name == "zoom_fit":
        arrows = _polygon((3, 12), (8, 7), (8, 17)) + _polygon((21, 12), (16, 7), (16, 17))
        return arrows + _roundedRect(7.5, 11, 9, 2, 0.5)
    if name == "follow":
        return _roundedRect(4, 4, 2.5, 16) + _roundedRect(9, 11, 7, 2, 0.5) + _polygon((15, 6.5), (21, 12), (15, 17.5))
    if name == "theme":
        ring = QtGui.QPainterPath()
        ring.addEllipse(QtCore.QPointF(12, 12), 8, 8)
        half = QtGui.QPainterPath(QtCore.QPointF(12, 4))
        half.arcTo(4, 4, 16, 16, 90, 180)
        half.closeSubpath()
        return _stroked(ring) + half
    if name == "play":
        return _polygon((7, 4.5), (20, 12), (7, 19.5))
    if name == "pause":
        return _roundedRect(6, 5, 4.5, 14) + _roundedRect(13.5, 5, 4.5, 14)
    if name == "stop":
        return _roundedRect(6, 6, 12, 12, 2)
    if name == "start":
        return _roundedRect(5, 5, 2.5, 14) + _polygon((19.5, 5), (9.5, 12), (19.5, 19))
    if name == "loop":
        outline = QtGui.QPainterPath()
        outline.addRoundedRect(4, 7.5, 16, 10, 5, 5)
        return _stroked(outline) + _polygon((12, 3.5), (17, 7.5), (12, 11.5))
    if name == "volume":
        wave = QtGui.QPainterPath(QtCore.QPointF(16, 8.5))
        wave.quadTo(19, 12, 16, 15.5)
        return _polygon((3.5, 9), (7.5, 9), (12.5, 5), (12.5, 19), (7.5, 15), (3.5, 15)) + _stroked(wave)
    raise ValueError(f'Unknown icon "{name}"')


def _pixmap(name: str, color: QtGui.QColor) -> QtGui.QPixmap:
    """Draw an icon

    Parameters
    ----------
    name : str
        The icon, see _shape
    color : QtGui.QColor
        The colour

    Returns
    -------
    QtGui.QPixmap
        The icon, large enough to stay sharp on high-resolution screens
    """
    pixmap = QtGui.QPixmap(72, 72)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.scale(3, 3)
    painter.fillPath(_shape(name), color)
    painter.end()
    return pixmap


class ToolBarButton(QtWidgets.QToolButton):
    """Button of a toolbar: an icon drawn in the colours of the current theme

    Parameters
    ----------
    icon_name : str
        The icon, see transport_icon
    tooltip : str
        What the button does
    action : str
        The name of the action, which gives the keyboard shortcut (see spiny.gui.shortcuts)
    color_name : str, optional
        The name of the colour of the icon in the theme. (default: "button_text")
    """

    def __init__(self, icon_name: str, tooltip: str, action: str, color_name: str = "button_text") -> None:
        super().__init__()
        self._icon_name = icon_name
        self._color_name = color_name
        self.setIconSize(QtCore.QSize(22, 22))
        key = shortcut(action)
        key_name = key.toString(QtGui.QKeySequence.SequenceFormat.NativeText)
        self.setToolTip(f"{tooltip} ({key_name})" if key_name else tooltip)
        # NOTE: not setShortcut, which delays the click by 100 ms. Typing in a text field still goes to the field
        self._shortcut = QtGui.QShortcut(key, self, self.click)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.applyTheme()

    def setIconName(self, icon_name: str) -> None:
        """Change the icon

        Parameters
        ----------
        icon_name : str
            The icon, see transport_icon
        """
        # NOTE: setting an icon repaints the button, even when it is the same one
        if icon_name != self._icon_name:
            self._icon_name = icon_name
            self.applyTheme()

    def applyTheme(self) -> None:
        """Draw the icon with the colours of the current theme"""
        self.setIcon(transport_icon(self._icon_name, theme.color(self._color_name), theme.color("accent_text")))


def transport_icon(name: str, color: QtGui.QColor, checked_color: QtGui.QColor | None = None) -> QtGui.QIcon:
    """Build an icon of the player toolbar

    Parameters
    ----------
    name : str
        The name of the icon, see _shape
    color : QtGui.QColor
        The colour
    checked_color : QtGui.QColor, optional
        The colour when the button is checked. (default: None, i.e. the same)

    Returns
    -------
    QtGui.QIcon
        The icon
    """
    icon = QtGui.QIcon(_pixmap(name, color))
    if checked_color is not None:
        icon.addPixmap(_pixmap(name, checked_color), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.On)
    return icon
