"""The panel of the parametric equalizer: the response curve with a handle per band, and the controls of a band"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from spiny.gui import theme
from spiny.gui.helpers.widgets import LabelledSlider

from .equalizer import EqBand, frequency_response
from .player import player

MIN_FREQUENCY = 20.0
MAX_FREQUENCY = 20000.0
MAX_GAIN_DB = 18.0

#: The names of the kinds of band, as shown in the panel
BAND_KINDS = {"peak": "Bell", "low_shelf": "Low shelf", "high_shelf": "High shelf"}


def band_color(index: int) -> QtGui.QColor:
    """Give the colour of a band

    Parameters
    ----------
    index : int
        The band

    Returns
    -------
    QtGui.QColor
        The colour (they come back after six bands)
    """
    return theme.color(f"eq_band_{index % 6 + 1}")


class EqNode(pg.TargetItem):
    """Handle of a band: it can be dragged, clicked, removed (right click, double click) and its wheel changes the Q"""

    clicked = QtCore.Signal()
    removeRequested = QtCore.Signal()
    wheeled = QtCore.Signal(int)

    def mouseClickEvent(self, ev: Any) -> None:
        """Select the band, or ask to remove it

        Parameters
        ----------
        ev : MouseClickEvent
            The click event
        """
        ev.accept()
        if ev.button() == QtCore.Qt.MouseButton.RightButton or ev.double():
            self.removeRequested.emit()
        else:
            self.clicked.emit()

    def wheelEvent(self, ev: Any) -> None:
        """Report a turn of the wheel

        Parameters
        ----------
        ev : QtWidgets.QGraphicsSceneWheelEvent
            The wheel event
        """
        ev.accept()
        self.wheeled.emit(ev.delta())


class EqPlot(pg.PlotWidget):
    """The response of the equalizer: the total as a filled curve, each band as a thin one, with its handle"""

    bandMoved = QtCore.Signal(int, float, float)  # The band, its frequency and its gain
    bandClicked = QtCore.Signal(int)
    bandRemoved = QtCore.Signal(int)
    bandWheeled = QtCore.Signal(int, int)  # The band and the turn of the wheel
    bandAdded = QtCore.Signal(float, float)  # The frequency and the gain

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(210)
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.setYRange(-MAX_GAIN_DB - 2, MAX_GAIN_DB + 2, padding=0)
        self.setToolTip("Double click: add a band\nHandle: drag to move, wheel for the Q, right click to remove")

        self._selected: int | None = None
        self._updating = False  # True while the handles are placed from the bands: not a change from the user
        self._nodes: list[EqNode] = []
        self._band_curves: list[pg.PlotCurveItem] = []

        ticks = [(50, "50"), (100, "100"), (200, "200"), (500, "500"), (1000, "1k"), (2000, "2k"), (5000, "5k")]
        ticks.append((10000, "10k"))
        self.getAxis("bottom").setTicks([[(np.log10(f), label) for f, label in ticks]])
        self.getAxis("left").setTicks([[(gain, f"{gain:+d}" if gain else "0") for gain in range(-18, 19, 6)]])
        self.getAxis("left").setWidth(30)

        # The grid: pairs of points, each pair being a line
        lines = [20, 30, 40, 50, 60, 70, 80, 90, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        lines += [2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 20000]
        vertical = np.repeat(np.log10(lines), 2), np.tile([-MAX_GAIN_DB - 2, MAX_GAIN_DB + 2], len(lines))
        gains = np.arange(-18, 19, 6)
        horizontal = np.tile(np.log10([MIN_FREQUENCY, MAX_FREQUENCY]), len(gains)), np.repeat(gains, 2)
        self._grid = pg.PlotCurveItem(
            np.concatenate([vertical[0], horizontal[0]]), np.concatenate([vertical[1], horizontal[1]]), connect="pairs"
        )
        self._zero = pg.PlotCurveItem(np.log10([MIN_FREQUENCY, MAX_FREQUENCY]), [0.0, 0.0])
        self._curve = pg.PlotCurveItem(fillLevel=0.0, antialias=True)
        for z_value, item in ((-20, self._grid), (-19, self._zero), (10, self._curve)):
            item.setZValue(z_value)
            self.addItem(item)

        self.scene().sigMouseClicked.connect(self._onClicked)
        self.applyTheme()

    def applyTheme(self) -> None:
        """Draw everything with the colours of the current theme"""
        self.setBackground(theme.color("eq_background"))
        self._grid.setPen(pg.mkPen(theme.color("eq_grid"), width=1))
        self._zero.setPen(pg.mkPen(theme.color("eq_zero_line"), width=1))
        self._curve.setPen(pg.mkPen(theme.color("eq_curve"), width=2.5))
        self._curve.setBrush(theme.color("eq_fill"))
        for name in ("left", "bottom"):
            axis = self.getAxis(name)
            axis.setPen(pg.mkPen(None))  # Only the labels: the grid already gives the lines
            axis.setTextPen(theme.color("eq_text"))
            axis.setStyle(tickLength=0)
        self._styleBands()

    def _styleBands(self) -> None:
        """Draw the handles and the curves of the bands, the selected one standing out"""
        for index, (node, curve) in enumerate(zip(self._nodes, self._band_curves)):
            selected = index == self._selected
            color = band_color(index)
            node.setBrush(color)
            node.setPen(pg.mkPen(theme.color("eq_node_border"), width=2.5 if selected else 1))
            node.setHoverBrush(color.lighter(130))
            node.setHoverPen(pg.mkPen(theme.color("eq_node_border"), width=2.5))
            node.scale = 15 if selected else 11
            node.viewTransformChanged()  # NOTE: the shape of the item depends on its size, and it is cached

            line, fill = QtGui.QColor(color), QtGui.QColor(color)
            line.setAlpha(230 if selected else 110)
            fill.setAlpha(50 if selected else 0)
            curve.setPen(pg.mkPen(line, width=1.5))
            curve.setBrush(fill)
            curve.setFillLevel(0.0 if selected else None)

    def _setBandCount(self, count: int) -> None:
        """Make as many handles and curves as there are bands

        Parameters
        ----------
        count : int
            The number of bands
        """
        while len(self._nodes) > count:
            self.removeItem(self._nodes.pop())
            self.removeItem(self._band_curves.pop())
        while len(self._nodes) < count:
            index = len(self._nodes)
            node = EqNode(symbol="o", size=11)
            node.setZValue(20)
            node.sigPositionChanged.connect(lambda _, index=index: self._onNodeMoved(index))
            node.clicked.connect(lambda index=index: self.bandClicked.emit(index))
            node.removeRequested.connect(lambda index=index: self.bandRemoved.emit(index))
            node.wheeled.connect(lambda delta, index=index: self.bandWheeled.emit(index, delta))
            curve = pg.PlotCurveItem(antialias=True)
            curve.setZValue(5)
            self.addItem(curve)
            self.addItem(node)
            self._nodes.append(node)
            self._band_curves.append(curve)

    def showBands(self, bands: list[EqBand], selected: int | None, rate: float, enabled: bool) -> None:
        """Show the bands

        Parameters
        ----------
        bands : list(EqBand)
            The bands
        selected : int or None
            The selected band
        rate : float
            The sampling rate, in Hz
        enabled : bool
            False if the equalizer is bypassed
        """
        top = min(MAX_FREQUENCY, rate / 2)
        frequencies = np.geomspace(MIN_FREQUENCY, top, 256)
        positions = np.log10(frequencies)
        self._selected = selected
        self._setBandCount(len(bands))

        self._updating = True
        self.setXRange(np.log10(MIN_FREQUENCY), np.log10(top), padding=0)
        for node, curve, band in zip(self._nodes, self._band_curves, bands):
            node.setPos(np.log10(min(band.frequency, top)), band.gain_db)
            node.setVisible(band.enabled)
            curve.setVisible(band.enabled and enabled)
            curve.setData(positions, 20.0 * np.log10(np.abs(frequency_response([band], rate, frequencies))))
        self._updating = False

        self._styleBands()
        self._curve.setData(positions, player.equalizer.responseDb(frequencies))

    def _onNodeMoved(self, index: int) -> None:
        """Report a handle which has been dragged

        Parameters
        ----------
        index : int
            The band
        """
        if not self._updating:
            position = self._nodes[index].pos()
            frequency = min(max(10.0 ** position.x(), MIN_FREQUENCY), MAX_FREQUENCY)
            self.bandMoved.emit(index, frequency, min(max(position.y(), -MAX_GAIN_DB), MAX_GAIN_DB))

    def _onClicked(self, ev: Any) -> None:
        """Ask for a new band on a double click on the curve area

        Parameters
        ----------
        ev : MouseClickEvent
            The click event
        """
        view = self.getViewBox()
        if ev.isAccepted() or not ev.double() or ev.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        if view.sceneBoundingRect().contains(ev.scenePos()):
            position = view.mapSceneToView(ev.scenePos())
            frequency = min(max(10.0 ** position.x(), MIN_FREQUENCY), MAX_FREQUENCY)
            self.bandAdded.emit(frequency, min(max(position.y(), -MAX_GAIN_DB), MAX_GAIN_DB))


class ParametricEqWidget(QtWidgets.QGroupBox):
    """Parametric equalizer: every change is heard at once, there is nothing to apply

    Bands can be added and removed, on the curve or with the buttons. The controls below the curve act on the selected
    band.

    Parameters
    ----------
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    #: The number of steps of the frequency slider (which is logarithmic)
    FREQUENCY_STEPS = 400

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Parametric equalizer", parent)
        self._selected: int | None = 2 if len(player.equalizer.bands) > 2 else None
        self._updating = False  # True while the controls are updated from the bands: not a change from the user

        self._cEnabled = QtWidgets.QCheckBox("Enabled")
        self._cEnabled.setChecked(player.equalizer.enabled)
        self._cEnabled.toggled.connect(self._onEnabled)
        self._bFlat = QtWidgets.QPushButton("Flat")
        self._bFlat.setToolTip("Set the gain of every band to 0 dB")
        self._bFlat.setAutoDefault(False)
        self._bFlat.clicked.connect(self._onFlat)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(self._cEnabled)
        header.addStretch(1)
        header.addWidget(self._bFlat)

        self._plot = EqPlot()
        self._plot.bandMoved.connect(self._onBandMoved)
        self._plot.bandClicked.connect(self._select)
        self._plot.bandRemoved.connect(self._removeBand)
        self._plot.bandWheeled.connect(self._onBandWheeled)
        self._plot.bandAdded.connect(self._addBand)

        self._chips = QtWidgets.QHBoxLayout()
        self._chips.setSpacing(4)
        self._chip_group = QtWidgets.QButtonGroup(self)
        self._chip_group.idClicked.connect(self._select)
        self._bAdd = QtWidgets.QPushButton("+")
        self._bAdd.setToolTip("Add a band")
        self._bAdd.clicked.connect(self._addBandInLargestGap)
        self._bRemove = QtWidgets.QPushButton("−")
        self._bRemove.setToolTip("Remove the selected band")
        self._bRemove.clicked.connect(lambda: self._removeBand(self._selected))
        chip_row = QtWidgets.QHBoxLayout()
        chip_row.addLayout(self._chips)
        chip_row.addStretch(1)
        for button in (self._bAdd, self._bRemove):
            button.setAutoDefault(False)
            button.setFixedWidth(30)
            chip_row.addWidget(button)

        self._boxKind = QtWidgets.QComboBox()
        for kind, name in BAND_KINDS.items():
            self._boxKind.addItem(name, kind)
        self._boxKind.currentIndexChanged.connect(lambda _: self._changeBand(kind=self._boxKind.currentData()))
        self._cBand = QtWidgets.QCheckBox("On")
        self._cBand.setToolTip("Use the selected band")
        self._cBand.toggled.connect(lambda checked: self._changeBand(enabled=checked))
        band_row = QtWidgets.QHBoxLayout()
        band_row.addWidget(self._boxKind, 1)
        band_row.addWidget(self._cBand)

        self._sFrequency = LabelledSlider(
            0,
            self.FREQUENCY_STEPS,
            0,
            lambda step: self._describeFrequency(self._frequencyOfStep(step)),
            step=4,
            to_value=lambda frequency: self._stepOfFrequency(min(max(frequency, MIN_FREQUENCY), MAX_FREQUENCY)),
        )
        self._sGain = LabelledSlider(
            round(-10 * MAX_GAIN_DB),
            round(10 * MAX_GAIN_DB),
            0,
            lambda v: f"{v / 10:+.1f} dB",
            step=5,
            to_value=lambda gain: round(gain * 10),
        )
        self._sQ = LabelledSlider(1, 100, 7, lambda v: f"{v / 10:.1f}", to_value=lambda q: round(q * 10))
        self._sFrequency.valueChanged.connect(lambda step: self._changeBand(frequency=self._frequencyOfStep(step)))
        self._sGain.valueChanged.connect(lambda value: self._changeBand(gain_db=value / 10))
        self._sQ.valueChanged.connect(lambda value: self._changeBand(q=value / 10))

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)  # wider sliders
        form.addRow("Frequency", self._sFrequency)
        form.addRow("Gain", self._sGain)
        form.addRow("Q", self._sQ)
        self._band_controls = QtWidgets.QWidget()
        band_layout = QtWidgets.QVBoxLayout(self._band_controls)
        band_layout.setContentsMargins(0, 0, 0, 0)
        band_layout.addLayout(band_row)
        band_layout.addLayout(form)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self._plot)
        layout.addLayout(chip_row)
        layout.addWidget(self._band_controls)

        self.refresh()

    @staticmethod
    def _describeFrequency(frequency: float) -> str:
        """Give the text of a frequency

        Parameters
        ----------
        frequency : float
            The frequency, in Hz

        Returns
        -------
        str
            The text
        """
        return f"{frequency / 1000:.2f} kHz" if frequency >= 1000 else f"{frequency:.0f} Hz"

    def _frequencyOfStep(self, step: int) -> float:
        """Convert a position of the frequency slider into a frequency

        Parameters
        ----------
        step : int
            The position

        Returns
        -------
        float
            The frequency, in Hz
        """
        return MIN_FREQUENCY * (MAX_FREQUENCY / MIN_FREQUENCY) ** (step / self.FREQUENCY_STEPS)

    def _stepOfFrequency(self, frequency: float) -> int:
        """Convert a frequency into a position of the frequency slider

        Parameters
        ----------
        frequency : float
            The frequency, in Hz

        Returns
        -------
        int
            The position
        """
        return round(self.FREQUENCY_STEPS * np.log(frequency / MIN_FREQUENCY) / np.log(MAX_FREQUENCY / MIN_FREQUENCY))

    def applyTheme(self) -> None:
        """Colour the buttons of the bands: the colour of a band comes from its position, not from the style sheet"""
        for index, chip in enumerate(self._chip_group.buttons()):
            chip.setStyleSheet(theme.band_chip_style(band_color(index)))

    def _setChipCount(self, count: int) -> None:
        """Make as many buttons as there are bands

        Parameters
        ----------
        count : int
            The number of bands
        """
        buttons = self._chip_group.buttons()
        for chip in buttons[count:]:
            self._chip_group.removeButton(chip)
            self._chips.removeWidget(chip)
            chip.hide()
            chip.deleteLater()
        for index in range(len(buttons), count):
            chip = QtWidgets.QPushButton(str(index + 1))
            chip.setCheckable(True)
            chip.setAutoDefault(False)
            chip.setFixedSize(28, 24)
            chip.setToolTip(f"Select the band {index + 1}")
            self._chip_group.addButton(chip, index)
            self._chips.addWidget(chip)

    def refresh(self) -> None:
        """Show the bands in the curve and in the controls (also when the sampling rate has changed)"""
        equalizer = player.equalizer
        self._setChipCount(len(equalizer.bands))
        self.applyTheme()
        self._plot.showBands(equalizer.bands, self._selected, equalizer.rate, equalizer.enabled)

        self._bRemove.setEnabled(self._selected is not None)
        self._band_controls.setEnabled(self._selected is not None)
        if self._selected is None:
            return

        band = equalizer.bands[self._selected]
        self._updating = True
        self._chip_group.button(self._selected).setChecked(True)
        self._boxKind.setCurrentIndex(self._boxKind.findData(band.kind))
        self._cBand.setChecked(band.enabled)
        self._sFrequency.setValue(self._stepOfFrequency(band.frequency))
        self._sGain.setValue(round(band.gain_db * 10))
        self._sQ.setValue(round(band.q * 10))
        self._updating = False

    def _select(self, index: int) -> None:
        """Make a band the one the controls act on

        Parameters
        ----------
        index : int
            The band
        """
        self._selected = index
        self.refresh()

    def _changeBand(self, index: int | None = None, **changes: Any) -> None:
        """Change a band, which is heard at once

        Parameters
        ----------
        index : int, optional
            The band. (default: None, i.e. the selected one)
        changes : keyword arguments
            The fields of the band to change
        """
        index = self._selected if index is None else index
        if self._updating or index is None:
            return
        bands = list(player.equalizer.bands)
        bands[index] = dataclasses.replace(bands[index], **changes)
        player.equalizer.setBands(bands)
        self.refresh()

    def _addBand(self, frequency: float, gain_db: float) -> None:
        """Add a bell band and select it

        Parameters
        ----------
        frequency : float
            The frequency of the band, in Hz
        gain_db : float
            The gain of the band, in dB
        """
        bands = [*player.equalizer.bands, EqBand("peak", frequency, round(gain_db, 1), 1.0)]
        player.equalizer.setBands(bands)
        self._select(len(bands) - 1)

    def _addBandInLargestGap(self) -> None:
        """Add a band at 0 dB, where the bands are the farthest apart"""
        top = min(MAX_FREQUENCY, player.equalizer.rate / 2)
        edges = sorted([MIN_FREQUENCY, top, *(min(band.frequency, top) for band in player.equalizer.bands)])
        ratio, low = max((high / low, low) for low, high in zip(edges, edges[1:]))
        self._addBand(low * np.sqrt(ratio), 0.0)

    def _removeBand(self, index: int | None) -> None:
        """Remove a band

        Parameters
        ----------
        index : int or None
            The band
        """
        if index is None:
            return
        bands = list(player.equalizer.bands)
        del bands[index]
        player.equalizer.setBands(bands)
        self._selected = min(index, len(bands) - 1) if bands else None
        self.refresh()

    def _onBandMoved(self, index: int, frequency: float, gain_db: float) -> None:
        """Change the frequency and the gain of the band whose handle has been dragged

        Parameters
        ----------
        index : int
            The band
        frequency : float
            The new frequency, in Hz
        gain_db : float
            The new gain, in dB
        """
        self._selected = index
        self._changeBand(index, frequency=frequency, gain_db=round(gain_db, 1))

    def _onBandWheeled(self, index: int, delta: int) -> None:
        """Change the Q of a band with the wheel

        Parameters
        ----------
        index : int
            The band
        delta : int
            The turn of the wheel (120 for one notch)
        """
        self._selected = index
        q = player.equalizer.bands[index].q * 1.15 ** (delta / 120)
        self._changeBand(index, q=min(max(q, 0.1), 10.0))

    def _onEnabled(self, enabled: bool) -> None:
        """Bypass the equalizer or not

        Parameters
        ----------
        enabled : bool
            False to bypass it
        """
        player.equalizer.setEnabled(enabled)
        self.refresh()

    def _onFlat(self) -> None:
        """Set the gain of every band to 0 dB"""
        player.equalizer.setBands([dataclasses.replace(band, gain_db=0.0) for band in player.equalizer.bands])
        self.refresh()
