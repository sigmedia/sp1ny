from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets, isQObjectAlive

from spiny.core import DataController, player
from spiny.gui.helpers.widgets import LabelledSlider
from .extractor import DB_FLOOR, WINDOWS, SpectrogramSettings, SpectrumExtractor, compute_spectrogram

if TYPE_CHECKING:
    from .visualisation import SpectrogramPlotWidget


class _AnalysisSignals(QtCore.QObject):
    """Carries the end of a background analysis to the GUI thread

    A signal emitted from a worker thread is delivered (queued) in the thread of the receiver, so the
    result is always handled by the GUI thread.
    """

    finished = QtCore.Signal(object)


class SpectrumController(DataController):
    """Controller of the "Spectrogram" plugin: only the visible part of the signal is analysed, live

    - The display settings (frequency range, maximum level, dynamic range) are applied instantly.
    - A change of the visible range or of an analysis setting (window, window length, time step) starts
      a new analysis in a background thread: the current spectrogram stays visible until the new one is
      ready, and an analysis asked for in the meantime waits for it, so the view keeps being updated during
      a drag. Each analysis also covers a margin around the view, and only computes the frames it does not
      have yet. Nothing is computed if the current spectrogram covers the view and half of its margin.
    - When the visible range is longer than `max_duration`, nothing is computed: the spectrogram is freed
      and a message is shown instead, until the user zooms in.

    Parameters
    ----------
    extractor : SpectrumExtractor
        The spectrogram extractor
    widget : SpectrogramPlotWidget
        The widget rendering the spectrogram

    Attributes
    ----------
    max_duration : int
        The longest visible range for which a spectrogram is computed, in seconds
    """

    #: Delay between a change of the view or of a setting and the analysis: gathers one burst of mouse events
    ANALYSIS_DELAY_MS = 30

    #: The part computed on each side of the view, as a fraction of its width and in seconds at most
    MARGIN_FRACTION = 0.5
    MAX_MARGIN = 30.0

    def __init__(self, extractor: SpectrumExtractor, widget: SpectrogramPlotWidget) -> None:
        super().__init__("Spectrogram", extractor, widget, overlays="all")
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._signals = _AnalysisSignals()
        self._signals.finished.connect(self._onAnalysisFinished)

        # NOTE: not restarted by a change: during a drag, the view must keep being updated
        self._analysis_timer = QtCore.QTimer()
        self._analysis_timer.setSingleShot(True)
        self._analysis_timer.setInterval(self.ANALYSIS_DELAY_MS)
        self._analysis_timer.timeout.connect(self._requestAnalysis)

        self.max_duration = 30
        self._active = False  # True while the plugin is displayed
        self._wav_plot = None
        self._generation = 0  # incremented by every new analysis: only the latest one is shown
        self._running = False
        self._pending: tuple[SpectrogramSettings, float, float] | None = None  # requested during another analysis
        self._panel: QtWidgets.QWidget | None = None

    ###########################################################################
    # Analysis
    ###########################################################################

    def setWavPlot(self, wav_plot: pg.PlotWidget) -> None:
        """Define the waveform plot: it gives the time axis, so its visible range is the one to analyse

        Parameters
        ----------
        wav_plot : pg.PlotWidget
            The waveform plot
        """
        if wav_plot is not self._wav_plot:  # this method is called every time the plugin is selected
            wav_plot.getViewBox().sigXRangeChanged.connect(self._scheduleAnalysis)
        super().setWavPlot(wav_plot)

    def extract(self) -> None:
        """Show the spectrogram of the visible range now (blocking), with the settings of the panel

        Used when the plugin is selected or a new signal is loaded. Inconsistent settings are reported in
        a message box.
        """
        self._active = True
        self._cancelAnalyses()
        self._extractor.settings = self._panelSettings()
        start_time, end_time = self._visibleRange()
        if end_time - start_time > self.max_duration:
            self._hideSpectrogram(end_time - start_time)
        else:
            self._widget.setMessage("")
            try:
                self._extractor.extract(start_time, end_time)
            except ValueError as ex:
                QtWidgets.QMessageBox.warning(None, "Spectrogram configuration", str(ex))
                return
        self.refresh()

    def release(self) -> None:
        """Free the spectrogram and drop the background analyses (the plugin is not displayed anymore)"""
        self._active = False
        self._analysis_timer.stop()
        self._cancelAnalyses()
        super().release()

    def _visibleRange(self) -> tuple[float, float]:
        """Return the part of the signal which is visible

        Returns
        -------
        tuple(float, float)
            The (start, end) times, in seconds
        """
        (start_time, end_time), _ = self._wav_plot.getViewBox().viewRange()
        return max(start_time, 0.0), min(end_time, player.duration)

    def _cancelAnalyses(self) -> None:
        """Make the analysis in progress outdated and forget the one waiting"""
        self._generation += 1
        self._pending = None

    def _hideSpectrogram(self, visible_duration: float) -> None:
        """Free the spectrogram and explain why it is not shown

        Parameters
        ----------
        visible_duration : float
            The duration of the visible range, in seconds
        """
        super().release()
        self._widget.setMessage(
            f"The visible part lasts {visible_duration:.1f} s, more than the maximum of {self.max_duration} s.\n"
            "Zoom in to see the spectrogram."
        )

    def _scheduleAnalysis(self, *args: Any) -> None:
        """Start the delay before the next analysis, if it is not running already

        Parameters
        ----------
        args : list
            The arguments of the signal triggering the update (unused)
        """
        if self._active and not self._analysis_timer.isActive():
            self._analysis_timer.start()

    def _requestAnalysis(self) -> None:
        """Bring the spectrogram up to date with the visible range and the panel, in the background

        If an analysis is already running, the request waits for it to finish (only the latest request
        is kept).
        """
        start_time, end_time = self._visibleRange()
        if end_time - start_time > self.max_duration:
            self._cancelAnalyses()
            self._hideSpectrogram(end_time - start_time)
            return

        self._widget.setMessage("")
        settings = self._panelSettings()
        margin = min((end_time - start_time) * self.MARGIN_FRACTION, self.MAX_MARGIN)
        # NOTE: half of the margin is enough to wait for: the rest is seen while the next analysis is running
        needed = max(start_time - margin / 2, 0.0), min(end_time + margin / 2, player.duration)
        if self._extractor.covers(settings, *needed) and not self._running:
            return  # nothing would change
        self._pending = (settings, max(start_time - margin, 0.0), min(end_time + margin, player.duration))
        if not self._running:
            self._startAnalysis()

    def _startAnalysis(self) -> None:
        """Start the pending analysis in the background thread"""
        if self._pending is None:
            return
        settings, start_time, end_time = self._pending
        self._pending = None
        self._generation += 1
        generation = self._generation
        self._running = True
        self._setStatus("Updating…")

        previous = self._extractor.spectrogram if settings == self._extractor.settings else None
        future = self._executor.submit(
            compute_spectrogram, player.signal[:, 0], player.sampling_rate, settings, start_time, end_time, previous
        )
        future.add_done_callback(lambda done: self._signals.finished.emit((generation, settings, done)))

    def _onAnalysisFinished(self, result: tuple[int, SpectrogramSettings, Future]) -> None:
        """Show the result of a background analysis, unless it is outdated (runs in the GUI thread)

        Parameters
        ----------
        result : tuple(int, SpectrogramSettings, Future)
            The generation of the analysis, its settings and its future
        """
        generation, settings, future = result
        self._running = False
        self._setStatus("")
        if generation == self._generation:
            try:
                self._extractor.setResult(settings, future.result())
                self.refresh()
            except ValueError as ex:
                self._setStatus(str(ex))
        if self._pending is not None:
            self._startAnalysis()

    ###########################################################################
    # Control panel
    ###########################################################################

    def setControlPanel(self, panel: QtWidgets.QLayout) -> None:
        """Add the spectrogram panel: display settings (instant) and analysis settings (in the background)

        The sliders start from the current settings, so they are kept when the panel is rebuilt.

        Parameters
        ----------
        panel : QtWidgets.QLayout
            The layout receiving the panel
        """
        settings = self._extractor.settings
        frequency_range = self._widget.frequency_range
        min_db, max_db = self._widget.db_range
        nyquist = player.sampling_rate // 2

        # Display: instant
        # NOTE: the ranges keep 100 Hz between the bounds, so that pushing one bound never leaves its range
        self._min_frequency = LabelledSlider(0, nyquist - 100, int(frequency_range[0]), lambda v: f"{v} Hz", step=50)
        self._max_frequency = LabelledSlider(100, nyquist, int(frequency_range[1]), lambda v: f"{v} Hz", step=50)
        self._max_level = LabelledSlider(-40, 0, int(max_db), lambda v: f"{v} dB")
        self._dynamic_range = LabelledSlider(10, int(-DB_FLOOR), int(max_db - min_db), lambda v: f"{v} dB")
        self._min_frequency.valueChanged.connect(self._onMinFrequencyChanged)
        self._max_frequency.valueChanged.connect(self._onMaxFrequencyChanged)
        self._max_level.valueChanged.connect(self._applyDisplay)
        self._dynamic_range.valueChanged.connect(self._applyDisplay)

        display_layout = QtWidgets.QFormLayout()
        display_layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)  # wider sliders
        display_layout.addRow("Min frequency", self._min_frequency)
        display_layout.addRow("Max frequency", self._max_frequency)
        display_layout.addRow("Max level", self._max_level)
        display_layout.addRow("Dynamic range", self._dynamic_range)
        display_box = QtWidgets.QGroupBox("Display")
        display_box.setLayout(display_layout)

        # Analysis: in the background, after a short delay
        self._window = QtWidgets.QComboBox()
        self._window.addItems(list(WINDOWS))
        self._window.setCurrentText(settings.window)
        self._window_length = LabelledSlider(2, 100, int(settings.framelength), _describeWindowLength)
        self._time_step = LabelledSlider(1, 20, int(settings.frameshift), lambda v: f"{v} ms")
        self._max_duration = LabelledSlider(1, 600, self.max_duration, lambda v: f"{v} s")
        self._window.currentTextChanged.connect(self._scheduleAnalysis)
        self._window_length.valueChanged.connect(self._scheduleAnalysis)
        self._time_step.valueChanged.connect(self._scheduleAnalysis)
        self._max_duration.valueChanged.connect(self._onMaxDurationChanged)

        analysis_layout = QtWidgets.QFormLayout()
        analysis_layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)  # wider sliders
        analysis_layout.addRow("Window", self._window)
        analysis_layout.addRow("Window length", self._window_length)
        analysis_layout.addRow("Time step", self._time_step)
        analysis_layout.addRow("Max visible duration", self._max_duration)
        analysis_box = QtWidgets.QGroupBox("Analysis")
        analysis_box.setLayout(analysis_layout)

        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)

        self._panel = QtWidgets.QGroupBox("Spectrogram")
        layout = QtWidgets.QVBoxLayout(self._panel)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        layout.addWidget(display_box)
        layout.addWidget(analysis_box)
        layout.addWidget(self._status)
        panel.addWidget(self._panel)

    def _panelSettings(self) -> SpectrogramSettings:
        """Read the analysis settings from the panel (the current ones if the panel does not exist)

        Returns
        -------
        SpectrogramSettings
            The settings
        """
        if not self._panelIsAlive():
            return self._extractor.settings
        return SpectrogramSettings(
            frameshift=self._time_step.value(),
            framelength=self._window_length.value(),
            window=self._window.currentText(),
            max_frequency=max(self._max_frequency.value(), self._extractor.settings.max_frequency),
        )

    def _onMaxDurationChanged(self, value: int) -> None:
        """Change the longest visible range for which a spectrogram is computed

        Parameters
        ----------
        value : int
            The new maximum, in seconds
        """
        self.max_duration = value
        self._scheduleAnalysis()

    def _onMinFrequencyChanged(self, value: int) -> None:
        """Keep the frequency range non-empty (by pushing the max frequency up), then apply it

        Parameters
        ----------
        value : int
            The new min frequency, in Hz
        """
        if value >= self._max_frequency.value():
            self._max_frequency.setValue(value + 50)  # applies the display through _onMaxFrequencyChanged
        else:
            self._applyDisplay()

    def _onMaxFrequencyChanged(self, value: int) -> None:
        """Keep the frequency range non-empty (by pushing the min frequency down), then apply it

        Parameters
        ----------
        value : int
            The new max frequency, in Hz
        """
        if value <= self._min_frequency.value():
            self._min_frequency.setValue(value - 50)  # applies the display through _onMinFrequencyChanged
        else:
            self._applyDisplay()

    def _applyDisplay(self) -> None:
        """Apply the display settings; a frequency above the analysed ones also starts a new analysis"""
        max_frequency = self._max_frequency.value()
        max_level = self._max_level.value()
        db_range = (max(max_level - self._dynamic_range.value(), DB_FLOOR), max_level)
        self._widget.setDisplayRange((self._min_frequency.value(), max_frequency), db_range)
        if max_frequency > self._extractor.settings.max_frequency:
            self._scheduleAnalysis()

    def _setStatus(self, text: str) -> None:
        """Show a short message under the panel (if it is displayed)

        Parameters
        ----------
        text : str
            The message, empty to clear it
        """
        if self._panelIsAlive():
            self._status.setText(text)

    def _panelIsAlive(self) -> bool:
        """Tell if the panel exists (it is destroyed when another plugin is selected)

        Returns
        -------
        bool
            True if the panel widgets can be used
        """
        return self._panel is not None and isQObjectAlive(self._panel)


def _describeWindowLength(milliseconds: int) -> str:
    """Describe a window length, with the kind of spectrogram it gives

    Parameters
    ----------
    milliseconds : int
        The window length

    Returns
    -------
    str
        The text of the slider label
    """
    if milliseconds <= 10:
        return f"{milliseconds} ms (wideband)"
    if milliseconds >= 20:
        return f"{milliseconds} ms (narrowband)"
    return f"{milliseconds} ms"
