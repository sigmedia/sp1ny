"""Overlays: what is drawn over the plot of a visualisation plugin (formants, F0, a mask, ...)

Many overlays provide tracks, which are values in the unit of the y axis of the plot at regular times. To follow
the view in real time, the tracks are computed by chunks of `CHUNK_DURATION` seconds in background threads, those
closest to the view first, and the chunks are kept: a track only takes a few bytes per frame, and coming back to a
part of the signal needs no new analysis. Only the visible part of the tracks is given to the plot.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from typing import Any

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets, isQObjectAlive

from spiny.gui import theme
from spiny.gui.helpers.widgets import CompactList, LabelledSlider

from .wav import player

logger = logging.getLogger(__name__)

#: The largest relative change between two points of a track joined by the line
MAX_JOINED_JUMP = 0.25

#: The analyses of every overlay share these threads, to leave the others to the interface and the audio
_executor = ThreadPoolExecutor(max_workers=2)


def frame_hop(time_step: float, rate: int) -> int:
    """Give the number of samples between two frames

    Parameters
    ----------
    time_step : float
        The time between two frames, in milliseconds
    rate : int
        The sampling rate, in Hz

    Returns
    -------
    int
        The hop, in samples
    """
    return max(round(time_step * rate / 1000), 1)


def signal_frames(signal: np.ndarray, first_frame: int, last_frame: int, hop: int, length: int) -> np.ndarray:
    """Give frames of a signal, centred on multiples of the hop (the signal is zero outside of its samples)

    Parameters
    ----------
    signal : np.ndarray
        The signal, shape (nb_samples,)
    first_frame : int
        The first frame
    last_frame : int
        The frame after the last one
    hop : int
        The number of samples between two frames
    length : int
        The number of samples of a frame

    Returns
    -------
    np.ndarray
        The frames (a view on a copy of the samples which are needed), shape (last_frame - first_frame, length)
    """
    start = first_frame * hop - length // 2
    end = (last_frame - 1) * hop - length // 2 + length
    segment = np.zeros(end - start, dtype=np.float32)
    source_start, source_end = max(start, 0), min(end, signal.shape[0])
    if source_end > source_start:
        segment[source_start - start : source_end - start] = signal[source_start:source_end]
    return np.lib.stride_tricks.sliding_window_view(segment, length)[::hop]


def connected_points(values: np.ndarray) -> np.ndarray:
    """Tell which points of a track are joined to the next one by the line

    Parameters
    ----------
    values : np.ndarray
        The track

    Returns
    -------
    np.ndarray
        1 if the point is joined to the next one, 0 if there is a gap or a jump: a line across a jump is a vertical
        stroke which looks like data
    """
    current, following = values[:-1], values[1:]
    with np.errstate(invalid="ignore"):
        joined = np.abs(following - current) <= MAX_JOINED_JUMP * np.minimum(current, following)
    return np.append(joined, False).astype(np.int32)


class Overlay(QtCore.QObject):
    """An overlay plugin: what is drawn over the plot of a visualisation plugin, with its configuration panel

    Parameters
    ----------
    name : str
        The name of the overlay, as displayed in the list of the overlays
    """

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.enabled = False
        self._plot: Any = None
        self._wav_plot: Any = None
        self._items: list[Any] = []

    @property
    def name(self) -> str:
        """str: The name of the overlay, as displayed in the list of the overlays"""
        return self._name

    @property
    def is_active(self) -> bool:
        """bool: True if the overlay is to be shown: it is enabled, and the visualisation plugin plots something"""
        return self.enabled and self._plot is not None and self._plot.isPlotting()

    def buildPanel(self) -> QtWidgets.QWidget:
        """Create the configuration panel of the overlay

        Returns
        -------
        QtWidgets.QWidget
            The panel
        """
        raise NotImplementedError

    def resetConfiguration(self) -> None:
        """Go back to the default configuration (whether the overlay is shown does not change)"""
        raise NotImplementedError

    def applyTheme(self) -> None:
        """Draw the overlay with the colours of the current theme"""

    def _createItems(self) -> list[Any]:
        """Create what is added to the plot

        Returns
        -------
        list(pg.GraphicsObject)
            The graphics items
        """
        raise NotImplementedError

    def _update(self) -> None:
        """Show or hide the items, depending on `is_active`"""
        raise NotImplementedError

    def _onViewChanged(self, *args: Any) -> None:
        """Follow the view

        Parameters
        ----------
        args : list
            The arguments of the signal (unused)
        """
        raise NotImplementedError

    def setEnabled(self, enabled: bool) -> None:
        """Show the overlay or not

        Parameters
        ----------
        enabled : bool
            True to show it
        """
        self.enabled = enabled
        self._update()

    def setHost(self, plot: Any, wav_plot: Any) -> None:
        """Define the plot of the visualisation plugin to draw on

        Parameters
        ----------
        plot : spiny.gui.widgets.DataWidget or None
            The plot, None if the visualisation plugin does not support this overlay
        wav_plot : pg.PlotWidget
            The waveform plot: it gives the time axis
        """
        if plot is not self._plot:
            if self._plot is not None and isQObjectAlive(self._plot):
                self._plot.plottingChanged.disconnect(self._update)
                for item in self._items:
                    self._plot.removeItem(item)
            self._items = []
            self._plot = plot
            if plot is not None:
                plot.plottingChanged.connect(self._update)
                self._items = self._createItems()
                for item in self._items:
                    plot.addItem(item, ignoreBounds=True)
                self.applyTheme()

        if wav_plot is not self._wav_plot:
            if self._wav_plot is not None and isQObjectAlive(self._wav_plot):
                self._wav_plot.getViewBox().sigXRangeChanged.disconnect(self._onViewChanged)
            self._wav_plot = wav_plot
            wav_plot.getViewBox().sigXRangeChanged.connect(self._onViewChanged)

        self._update()

    def _visibleRange(self) -> tuple[float, float]:
        """Give the visible part of the signal

        Returns
        -------
        tuple(float, float)
            The (start, end) times, in seconds
        """
        (start, end), _ = self._wav_plot.getViewBox().viewRange()
        return max(start, 0.0), min(end, player.duration)


class TrackOverlay(Overlay):
    """An overlay made of tracks: subclasses give the tracks, the analysis and the configuration of the analysis

    Attributes
    ----------
    TRACKS : tuple(str)
        The names of the tracks: "overlay_<name in lower case>" in the theme gives their colour
    HIDDEN_TRACKS : tuple(str)
        The tracks which are not shown by default
    CHUNK_DURATION : float
        The duration analysed at once, in seconds
    MAX_RUNNING : int
        The number of chunks of an overlay being analysed at the same time
    MAX_DRAWN_POINTS : int
        The number of points of a track given to the plot at most (a screen has far fewer columns than a long view has
        frames)
    """

    TRACKS: tuple[str, ...] = ()
    HIDDEN_TRACKS: tuple[str, ...] = ()
    CHUNK_DURATION = 5.0
    MAX_RUNNING = 2
    MAX_DRAWN_POINTS = 4000
    DEFAULT_LINE_WIDTH = 2.0

    _chunkFinished = QtCore.Signal(object)  # NOTE: emitted by a worker thread, so delivered in the GUI thread

    def __init__(self, name: str, settings: Any) -> None:
        super().__init__(name)
        self._settings = settings
        self._default_settings = settings

        self._curves: dict[str, pg.PlotCurveItem] = {}
        self._shown = {track: track not in self.HIDDEN_TRACKS for track in self.TRACKS}
        self._colors: dict[str, QtGui.QColor] = {}  # The colours chosen by the user
        self._line_width = self.DEFAULT_LINE_WIDTH

        self._signal: np.ndarray | None = None
        self._chunks: dict[int, np.ndarray] = {}
        self._running: set[tuple[int, int]] = set()  # The (generation, chunk) being analysed
        self._generation = 0  # Incremented when the settings change: results of older analyses are dropped
        self._drawn: tuple[int, int, int] | None = None  # What the curves show: (first frame, last frame, stride)

        self._chunkFinished.connect(self._onChunkFinished)
        # Results come in bursts: drawing once per burst is enough
        self._draw_timer = QtCore.QTimer(self)
        self._draw_timer.setSingleShot(True)
        self._draw_timer.setInterval(30)
        self._draw_timer.timeout.connect(self._draw)

    @property
    def settings(self) -> Any:
        """Any: The parameters of the analysis"""
        return self._settings

    ###########################################################################
    # To be defined by the plugins
    ###########################################################################

    def compute(self, signal: np.ndarray, rate: int, settings: Any, first_frame: int, last_frame: int) -> np.ndarray:
        """Compute the tracks of some frames (in a background thread: only read the arguments)

        Parameters
        ----------
        signal : np.ndarray
            The whole (mono) signal
        rate : int
            The sampling rate, in Hz
        settings : Any
            The parameters of the analysis
        first_frame : int
            The first frame
        last_frame : int
            The frame after the last one

        Returns
        -------
        np.ndarray
            The tracks, shape (nb_frames, nb_tracks), NaN where there is no value
        """
        raise NotImplementedError

    ###########################################################################
    # Configuration
    ###########################################################################

    def setSettings(self, settings: Any) -> None:
        """Change the parameters of the analysis: the tracks are computed again, the old ones staying until then

        Parameters
        ----------
        settings : Any
            The parameters
        """
        if settings != self._settings:
            self._settings = settings
            self._forgetChunks()
            self._update()

    def resetConfiguration(self) -> None:
        """Go back to the default analysis and look (whether the overlay is shown does not change)"""
        self._shown = {track: track not in self.HIDDEN_TRACKS for track in self.TRACKS}
        self._colors = {}
        self._line_width = self.DEFAULT_LINE_WIDTH
        self.applyTheme()
        self.setSettings(self._default_settings)
        self._update()

    def color(self, track: str) -> QtGui.QColor:
        """Give the colour of a track

        Parameters
        ----------
        track : str
            The name of the track

        Returns
        -------
        QtGui.QColor
            The colour
        """
        return self._colors.get(track, theme.color(f"overlay_{track.lower()}"))

    def setColor(self, track: str, color: QtGui.QColor) -> None:
        """Change the colour of a track

        Parameters
        ----------
        track : str
            The name of the track
        color : QtGui.QColor
            The colour
        """
        self._colors[track] = color
        self.applyTheme()

    def isTrackShown(self, track: str) -> bool:
        """Tell if a track is shown

        Parameters
        ----------
        track : str
            The name of the track

        Returns
        -------
        bool
            True if it is shown
        """
        return self._shown[track]

    def setTrackShown(self, track: str, shown: bool) -> None:
        """Show a track or not

        Parameters
        ----------
        track : str
            The name of the track
        shown : bool
            True to show it
        """
        self._shown[track] = shown
        self._update()

    @property
    def line_width(self) -> float:
        """float: The width of the lines, in pixels"""
        return self._line_width

    def setLineWidth(self, width: float) -> None:
        """Change the width of the lines

        Parameters
        ----------
        width : float
            The width, in pixels
        """
        self._line_width = width
        self.applyTheme()

    def applyTheme(self) -> None:
        """Draw the tracks with their colours"""
        for track, curve in self._curves.items():
            curve.setPen(pg.mkPen(self.color(track), width=self._line_width))

    def setHost(self, plot: Any, wav_plot: Any) -> None:
        """Define the plot to draw on, see Overlay.setHost; a new file also makes the tracks outdated

        Parameters
        ----------
        plot : spiny.gui.widgets.DataWidget or None
            The plot
        wav_plot : pg.PlotWidget
            The waveform plot
        """
        if player.signal is not self._signal:
            self._signal = player.signal
            self._forgetChunks()
        if plot is None:
            self._curves = {}
        super().setHost(plot, wav_plot)

    def _createItems(self) -> list[Any]:
        """Create one curve per track

        Returns
        -------
        list(pg.PlotCurveItem)
            The curves
        """
        self._curves = {track: pg.PlotCurveItem(connect="finite") for track in self.TRACKS}
        self._drawn = None
        for curve in self._curves.values():
            curve.setZValue(5)  # NOTE: above the image and the mask, below the playhead
        return list(self._curves.values())

    def _update(self) -> None:
        """Show or hide the curves, and start what is missing if the overlay is shown"""
        active = self.is_active
        for track, curve in self._curves.items():
            curve.setVisible(active and self._shown[track])
        if active:
            self._analyse()
            self._drawn = None
            self._draw()

    def _forgetChunks(self) -> None:
        """Forget what has been analysed, also what is being analysed"""
        self._generation += 1
        self._chunks = {}

    ###########################################################################
    # Analysis
    ###########################################################################

    def _frameRate(self) -> tuple[int, int]:
        """Give the time grid of the tracks

        Returns
        -------
        int
            The hop, in samples
        int
            The number of frames in a chunk
        """
        hop = frame_hop(self._settings.time_step, player.sampling_rate)
        return hop, max(round(self.CHUNK_DURATION * player.sampling_rate / hop), 1)

    def _analyse(self) -> None:
        """Start the analysis of the chunks missing around the view, the closest ones first"""
        start, end = self._visibleRange()
        hop, chunk_frames = self._frameRate()
        rate = player.sampling_rate
        margin = end - start  # NOTE: what follows is computed in advance: a pan then shows it at once
        chunk_duration = chunk_frames * hop / rate
        nb_chunks = (player.signal.shape[0] // hop) // chunk_frames + 1
        first = max(int((start - margin) / chunk_duration), 0)
        last = min(int((end + margin) / chunk_duration) + 1, nb_chunks)
        centre = (start + end) / 2 / chunk_duration
        running = {chunk for generation, chunk in self._running if generation == self._generation}
        missing = [c for c in range(first, last) if c not in self._chunks and c not in running]
        missing.sort(key=lambda chunk: abs(chunk + 0.5 - centre))

        nb_frames = player.signal.shape[0] // hop + 1
        for chunk in missing[: max(self.MAX_RUNNING - len(self._running), 0)]:
            key = (self._generation, chunk)
            self._running.add(key)
            future = _executor.submit(
                self.compute,
                player.signal[:, 0],
                rate,
                self._settings,
                chunk * chunk_frames,
                min((chunk + 1) * chunk_frames, nb_frames),
            )
            future.add_done_callback(partial(self._emitChunkFinished, key))

    def _emitChunkFinished(self, key: tuple[int, int], future: Future) -> None:
        """Report the end of an analysis to the GUI thread (runs in the worker thread)

        Parameters
        ----------
        key : tuple(int, int)
            The (generation, chunk)
        future : Future
            The future of the analysis
        """
        self._chunkFinished.emit((key, future))

    def _onChunkFinished(self, result: tuple[tuple[int, int], Future]) -> None:
        """Keep the result of a chunk, unless it is outdated (runs in the GUI thread)

        Parameters
        ----------
        result : tuple(tuple(int, int), Future)
            The (generation, chunk), and the future of the analysis
        """
        key, future = result
        self._running.discard(key)
        generation, chunk = key
        if generation == self._generation:
            exception = future.exception()
            if exception is None:
                self._chunks[chunk] = future.result()
            else:
                logger.error('The analysis of the overlay "%s" failed', self._name, exc_info=exception)
                self._chunks[chunk] = np.full((1, len(self.TRACKS)), np.nan, dtype=np.float32)  # Not to try forever
            self._drawn = None
            self._draw_timer.start()
        if self.is_active:
            self._analyse()

    ###########################################################################
    # Drawing
    ###########################################################################

    def _onViewChanged(self, *args: Any) -> None:
        """Follow the view

        Parameters
        ----------
        args : list
            The arguments of the signal (unused)
        """
        if self.is_active:
            self._analyse()
            self._draw()

    def _draw(self) -> None:
        """Give the plot the part of the tracks around the view, unless it already has it"""
        if not self.is_active or player.signal.shape[0] == 0:
            return

        start, end = self._visibleRange()
        hop, chunk_frames = self._frameRate()
        rate = player.sampling_rate
        first = int(start * rate / hop)
        last = int(np.ceil(end * rate / hop)) + 1
        stride = max((last - first) // self.MAX_DRAWN_POINTS, 1)
        if self._drawn is not None:
            drawn_first, drawn_last, drawn_stride = self._drawn
            if drawn_first <= first and last <= drawn_last and drawn_stride == stride:
                return

        # NOTE: half a view more on each side, so that small pans do not need any drawing
        margin = (last - first) // 2
        first = max(first - margin, 0) // stride * stride
        last += margin
        self._drawn = (first, last, stride)
        frames = np.arange(first, last, stride)
        values = np.full((frames.size, len(self.TRACKS)), np.nan, dtype=np.float32)
        for chunk, tracks in self._chunks.items():
            chunk_start = chunk * chunk_frames
            indices = (frames >= chunk_start) & (frames < chunk_start + tracks.shape[0])
            if indices.any():
                values[indices, : tracks.shape[1]] = tracks[frames[indices] - chunk_start]

        times = frames * hop / rate
        for index, track in enumerate(self.TRACKS):
            self._curves[track].setData(times, values[:, index], connect=connected_points(values[:, index]))


class OverlayPanel(QtWidgets.QWidget):
    """The overlay tab: on top the overlays which can be shown, below the configuration of the highlighted one"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._list = CompactList()
        self._list.setToolTip("Tick an overlay to show it, select it to configure it")
        self._list.itemChanged.connect(self._onItemChanged)
        self._list.currentRowChanged.connect(self._showCurrentPanel)
        self._none = QtWidgets.QLabel("The current visualisation does not support any overlay.")
        self._none.setWordWrap(True)
        self._panels = {name: overlay.buildPanel() for name, overlay in overlay_entry_dict.items()}

        self._bReset = QtWidgets.QPushButton("Reset to defaults")
        self._bReset.setToolTip("Go back to the default configuration of the selected overlay")
        self._bReset.setAutoDefault(False)
        self._bReset.clicked.connect(self._resetCurrent)

        content = QtWidgets.QWidget()
        layout = self._layout = QtWidgets.QVBoxLayout(content)
        layout.addWidget(self._list)
        layout.addWidget(self._none)
        for panel in self._panels.values():
            layout.addWidget(panel)
            panel.hide()  # NOTE: hidden and not in a stacked widget: the group only takes the height it needs
        layout.addWidget(self._bReset)
        layout.addStretch(1)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def setVisualisation(self, controller: Any, wav_plot: Any) -> None:
        """Offer the overlays supported by a visualisation plugin, and draw them on its plot

        Parameters
        ----------
        controller : spiny.core.DataController
            The controller of the visualisation plugin
        wav_plot : pg.PlotWidget
            The waveform plot
        """
        current = self._list.currentItem().text() if self._list.currentItem() else None
        self._list.blockSignals(True)
        self._list.clear()
        for name, overlay in overlay_entry_dict.items():
            supported = controller.supportsOverlay(name)
            overlay.setHost(controller.widget if supported else None, wav_plot)
            if supported:
                item = QtWidgets.QListWidgetItem(name, self._list)
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Checked if overlay.enabled else QtCore.Qt.CheckState.Unchecked)
                if name == current:
                    self._list.setCurrentItem(item)
        if self._list.count() and self._list.currentItem() is None:
            self._list.setCurrentRow(0)
        self._list.blockSignals(False)

        self._list.setVisible(self._list.count() > 0)
        self._none.setVisible(self._list.count() == 0)
        self._bReset.setVisible(self._list.count() > 0)
        self._showCurrentPanel()

    def _onItemChanged(self, item: QtWidgets.QListWidgetItem) -> None:
        """Show an overlay which has been ticked, or hide it

        Parameters
        ----------
        item : QtWidgets.QListWidgetItem
            The entry of the overlay
        """
        overlay_entry_dict[item.text()].setEnabled(item.checkState() == QtCore.Qt.CheckState.Checked)

    def _showCurrentPanel(self, *args: Any) -> None:
        """Show the configuration of the highlighted overlay

        Parameters
        ----------
        args : list
            The arguments of the signal (unused)
        """
        current = self._list.currentItem().text() if self._list.currentItem() else None
        for name, panel in self._panels.items():
            panel.setVisible(name == current)

    def _resetCurrent(self) -> None:
        """Go back to the default configuration of the highlighted overlay, and show it in a new panel"""
        name = self._list.currentItem().text()
        overlay_entry_dict[name].resetConfiguration()
        panel = overlay_entry_dict[name].buildPanel()
        self._layout.replaceWidget(self._panels[name], panel)
        self._panels[name].hide()
        self._panels[name].deleteLater()
        self._panels[name] = panel
        self._showCurrentPanel()

    def applyTheme(self) -> None:
        """Follow the theme: the colours of the tracks which were not chosen by the user come from it"""
        for overlay in overlay_entry_dict.values():
            overlay.applyTheme()


overlay_entry_dict: dict[str, Overlay] = dict()


def register_overlay(overlay: Overlay) -> None:
    """Register an overlay plugin under its name

    Parameters
    ----------
    overlay : Overlay
        The overlay

    Raises
    ------
    ValueError
        if an overlay with the same name is already registered
    """
    if overlay.name in overlay_entry_dict:
        raise ValueError(f'An overlay named "{overlay.name}" is already registered')
    overlay_entry_dict[overlay.name] = overlay


def track_display_box(overlay: TrackOverlay, tracks: tuple[str, ...]) -> QtWidgets.QGroupBox:
    """Create the part of a configuration panel choosing the tracks to show and their look

    Parameters
    ----------
    overlay : TrackOverlay
        The overlay
    tracks : tuple(str)
        The tracks

    Returns
    -------
    QtWidgets.QGroupBox
        The group
    """
    grid = QtWidgets.QGridLayout()
    for row, track in enumerate(tracks):
        show = QtWidgets.QCheckBox(track)
        show.setChecked(overlay.isTrackShown(track))
        show.toggled.connect(partial(overlay.setTrackShown, track))
        swatch = ColorSwatch(overlay, track)
        grid.addWidget(show, row, 0)
        grid.addWidget(swatch, row, 1)
    grid.setColumnStretch(1, 1)

    width = LabelledSlider(1, 6, round(overlay.line_width), lambda v: f"{v} px")
    width.valueChanged.connect(overlay.setLineWidth)
    grid.addWidget(QtWidgets.QLabel("Line width"), len(tracks), 0)
    grid.addWidget(width, len(tracks), 1)

    box = QtWidgets.QGroupBox("Display")
    box.setLayout(grid)
    return box


class ColorSwatch(QtWidgets.QPushButton):
    """Button showing the colour of a track: a click opens the colour dialog

    Parameters
    ----------
    overlay : Any
        The overlay: it provides color(name) and setColor(name, color)
    track : str
        The name of what is coloured
    """

    def __init__(self, overlay: Any, track: str) -> None:
        super().__init__()
        self._overlay = overlay
        self._track = track
        self.setAutoDefault(False)
        self.setFixedHeight(20)
        self.setToolTip(f"Choose the colour of {track}")
        self.clicked.connect(self._choose)
        self.applyTheme()

    def applyTheme(self) -> None:
        """Show the colour of the track"""
        self.setStyleSheet(theme.color_swatch_style(self._overlay.color(self._track)))

    def _choose(self) -> None:
        """Ask for a colour"""
        color = QtWidgets.QColorDialog.getColor(self._overlay.color(self._track), self, f"Colour of {self._track}")
        if color.isValid():
            self._overlay.setColor(self._track, color)
            self.applyTheme()
