"""Icons of the player toolbar, drawn as vector shapes so that they look the same on every system"""

from __future__ import annotations

from pyqtgraph.Qt import QtCore, QtGui


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


def _shape(name: str) -> QtGui.QPainterPath:
    """Build the shape of an icon

    Parameters
    ----------
    name : str
        "play", "pause", "stop", "start", "loop" or "volume"

    Returns
    -------
    QtGui.QPainterPath
        The shape, on a 24 × 24 grid
    """
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


def transport_icon(name: str, color: QtGui.QColor, checked_color: QtGui.QColor | None = None) -> QtGui.QIcon:
    """Build an icon of the player toolbar

    Parameters
    ----------
    name : str
        "play", "pause", "stop", "start", "loop" or "volume"
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
