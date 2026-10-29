from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

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
    """Controller of the "Spectrogram" plugin: a control panel which updates the spectrogram live

    - The display settings (frequency range, maximum level, dynamic range) are applied instantly.
    - The analysis settings (window, window length, time step) start a new analysis in a background
      thread, `ANALYSIS_DELAY_MS` after the last change: the current spectrogram stays visible until
      the new one is ready, and the result of an outdated analysis is dropped.

    Parameters
    ----------
    extractor : SpectrumExtractor
        The spectrogram extractor
    widget : SpectrogramPlotWidget
        The widget rendering the spectrogram
    """

    #: Delay between the last change of an analysis setting and the start of the analysis
    ANALYSIS_DELAY_MS = 300

    def __init__(self, extractor: SpectrumExtractor, widget: SpectrogramPlotWidget) -> None:
        super().__init__("Spectrogram", extractor, widget)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._signals = _AnalysisSignals()
        self._signals.finished.connect(self._onAnalysisFinished)

        # Restarted at every change, so that dragging a slider starts a single analysis
        self._analysis_timer = QtCore.QTimer()
        self._analysis_timer.setSingleShot(True)
        self._analysis_timer.setInterval(self.ANALYSIS_DELAY_MS)
        self._analysis_timer.timeout.connect(self._requestAnalysis)

        self._generation = 0  # incremented by every new analysis: only the latest one is shown
        self._running = False
        self._pending: SpectrogramSettings | None = None  # requested while another analysis was running
        self._panel: QtWidgets.QWidget | None = None

    ###########################################################################
    # Analysis
    ###########################################################################

    def extract(self) -> None:
        """Compute the spectrogram now (blocking) with the settings of the panel, and show it

        Used when the plugin is selected or a new signal is loaded. Inconsistent settings are reported in
        a message box.
        """
        self._generation += 1  # any background analysis in progress is now outdated
        self._pending = None
        self._extractor.settings = self._panelSettings()
        try:
            self._extractor.extract()
        except ValueError as ex:
            QtWidgets.QMessageBox.warning(None, "Spectrogram configuration", str(ex))
            return
        self.refresh()

    def release(self) -> None:
        """Free the spectrogram and drop the background analyses (the plugin is not displayed anymore)"""
        self._analysis_timer.stop()
        self._generation += 1
        self._pending = None
        super().release()

    def _requestAnalysis(self) -> None:
        """Analyse the signal again with the settings of the panel, in the background

        If an analysis is already running, the request waits for it to finish (only the latest request
        is kept).
        """
        settings = self._panelSettings()
        if settings == self._extractor.settings and not self._running:
            return  # nothing would change
        self._pending = settings
        if not self._running:
            self._startAnalysis()

    def _startAnalysis(self) -> None:
        """Start the pending analysis in the background thread"""
        settings, self._pending = self._pending, None
        if settings is None:
            return
        self._generation += 1
        generation = self._generation
        self._running = True
        self._setStatus("Updating…")

        future = self._executor.submit(compute_spectrogram, player.signal[:, 0], player.sampling_rate, settings)
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
                self._extractor.setResult(settings, *future.result())
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
        self._window.currentTextChanged.connect(self._analysis_timer.start)
        self._window_length.valueChanged.connect(self._analysis_timer.start)
        self._time_step.valueChanged.connect(self._analysis_timer.start)

        analysis_layout = QtWidgets.QFormLayout()
        analysis_layout.addRow("Window", self._window)
        analysis_layout.addRow("Window length", self._window_length)
        analysis_layout.addRow("Time step", self._time_step)
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
            self._analysis_timer.start()

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
