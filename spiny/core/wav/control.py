# Python
from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Python SoundDevice
import sounddevice as sd

# SpINY
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets, isQObjectAlive

from spiny.gui import theme
from spiny.gui.helpers.widgets import LabelledSlider
from spiny.gui.icons import ToolBarButton

from .equalizer_widget import ParametricEqWidget
from .player import player


def format_time(seconds: float) -> str:
    """Format a time for the time display

    Parameters
    ----------
    seconds : float
        The time, in seconds

    Returns
    -------
    str
        The time as minutes:seconds.milliseconds
    """
    milliseconds = round(seconds * 1000)
    return f"{milliseconds // 60000:02d}:{milliseconds // 1000 % 60:02d}.{milliseconds % 1000:03d}"


def output_devices() -> tuple[dict[str, int], str | None]:
    """List the audio output devices

    Returns
    -------
    dict(str, int)
        The PortAudio index of each output device, by name
    str or None
        The name of the default output device (its index is -1 when there is none)
    """
    devices = dict()
    default_index = sd.default.device[1]
    default_device = None
    for index, device in enumerate(sd.query_devices()):
        if device["max_output_channels"] <= 0:  # NOTE: only consider output devices!
            continue
        if "index" in device:
            index = int(device["index"])

        devices[device["name"]] = index
        if index == default_index:
            default_device = device["name"]
    return devices, default_device


class TransportWidget(QtWidgets.QWidget):
    """Transport of the player, as in a DAW: return to start, play/pause, stop, loop and the time display

    The state is polled from the player, so that the display is also right when the playback ends by itself or is
    started elsewhere (e.g. from an annotation).

    Parameters
    ----------
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    #: How far the rewind and forward buttons jump, in seconds
    SKIP_SECONDS = 1.0

    #: The playback speeds offered
    SPEEDS = (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._bStart = ToolBarButton("start", "Return to start", "go_to_start")
        self._bRewind = ToolBarButton("rewind", f"Back {self.SKIP_SECONDS:g} s", "rewind")
        self._bPlay = ToolBarButton("play", "Play / Pause", "play_pause", color_name="play")
        self._bStop = ToolBarButton("stop", "Stop", "stop")
        self._bForward = ToolBarButton("forward", f"Forward {self.SKIP_SECONDS:g} s", "forward")
        self._bEnd = ToolBarButton("end", "Go to the end", "go_to_end")
        self._bLoop = ToolBarButton("loop", "Loop", "loop")
        self._bSlower = ToolBarButton("minus", "Slower (the pitch follows)", "speed_down")
        self._bFaster = ToolBarButton("plus", "Faster (the pitch follows)", "speed_up")
        self._bLoop.setCheckable(True)
        self._bLoop.setChecked(player.loop_activated)
        self._bStart.clicked.connect(lambda: player.seek(0.0))
        self._bRewind.clicked.connect(lambda: player.seek(player.position - self.SKIP_SECONDS))
        self._bForward.clicked.connect(lambda: player.seek(player.position + self.SKIP_SECONDS))
        self._bEnd.clicked.connect(lambda: player.seek(player.duration))
        self._bSlower.clicked.connect(lambda: self.changeSpeed(-1))
        self._bFaster.clicked.connect(lambda: self.changeSpeed(1))
        self._bPlay.clicked.connect(self.playPause)
        self._bStop.clicked.connect(player.stop)
        self._bLoop.clicked.connect(player.toggleLoop)

        # NOTE: a fixed-width font, so that the digits do not move while the time changes
        time_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.SystemFont.FixedFont)
        time_font.setBold(True)
        self._lTime = QtWidgets.QLabel()
        self._lTime.setObjectName("time")
        self._lTime.setFont(time_font)
        self._lDuration = QtWidgets.QLabel()
        self._lDuration.setObjectName("duration")
        self._lDuration.setFont(time_font)
        self._lSpeed = QtWidgets.QLabel()
        self._lSpeed.setObjectName("speed")
        self._lSpeed.setFont(time_font)
        self._lSpeed.setToolTip("Playback speed")

        # Without any output device, playback controls are useless
        if not output_devices()[0]:
            for button in (
                self._bStart,
                self._bRewind,
                self._bPlay,
                self._bStop,
                self._bForward,
                self._bEnd,
                self._bLoop,
                self._bSlower,
                self._bFaster,
            ):
                button.setEnabled(False)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        for button in (self._bStart, self._bRewind, self._bPlay, self._bStop, self._bForward, self._bEnd, self._bLoop):
            layout.addWidget(button)
        layout.addSpacing(12)
        layout.addWidget(self._lTime)
        layout.addWidget(self._lDuration)
        layout.addSpacing(12)
        layout.addWidget(self._bSlower)
        layout.addWidget(self._lSpeed)
        layout.addWidget(self._bFaster)

        self._refresh()
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(30)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

    def _refresh(self) -> None:
        """Show the state of the player: position, duration and play or pause icon"""
        self._lTime.setText(format_time(player.position))
        self._lDuration.setText(format_time(player.duration))
        self._lSpeed.setText(f"{player.speed:.2f}x")
        self._bPlay.setIconName("pause" if player.is_playing and not player.is_paused else "play")

    def changeSpeed(self, direction: int) -> None:
        """Move to the next or previous playback speed

        Parameters
        ----------
        direction : int
            1 for the next faster speed, -1 for the next slower one
        """
        index = self.SPEEDS.index(player.speed) if player.speed in self.SPEEDS else self.SPEEDS.index(1.0)
        player.speed = self.SPEEDS[min(max(index + direction, 0), len(self.SPEEDS) - 1)]

    def playPause(self) -> None:
        """Play from the cursor, or pause/resume a playback (a message box reports a device which cannot play)"""
        if player.is_playing:
            player.pauseResume()
            return
        try:
            player.play()
        except sd.PortAudioError as ex:
            QtWidgets.QMessageBox.warning(self, "Playback error", f"The audio device cannot play this signal:\n{ex}")


class OutputWidget(QtWidgets.QWidget):
    """Output of the player: the audio device and the volume

    Parameters
    ----------
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Preferred)

        self._devices, default_device = output_devices()

        # Generation Device ComboBox
        self._boxDevices = QtWidgets.QComboBox()
        self._boxDevices.setToolTip("Output device")
        self._boxDevices.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        # NOTE: the name of a device can be very long, it must not decide the width of the toolbar
        self._boxDevices.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._boxDevices.setMinimumContentsLength(24)
        self._boxDevices.addItems(self._devices.keys())
        if default_device is not None:
            self._boxDevices.setCurrentText(default_device)

        if not self._devices:
            self._boxDevices.addItem("No output device")
            self._boxDevices.setEnabled(False)
        self._boxDevices.currentTextChanged.connect(self.device_changed)

        # Define volume slider
        self._bMute = ToolBarButton("volume", "Mute", "mute")
        self._bMute.setCheckable(True)
        self._bMute.setChecked(player.muted)
        self._bMute.toggled.connect(self.mute_changed)
        self._sVolume = LabelledSlider(0, 100, round(player.volume * 100), lambda v: f"{v}%", compact=True)
        self._sVolume.setFixedWidth(180)
        self._sVolume.setToolTip("Volume")
        self._sVolume.valueChanged.connect(self.volume_changed)
        self.volume_changed()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        layout.addWidget(self._boxDevices)
        layout.addSpacing(12)
        layout.addWidget(self._bMute)
        layout.addWidget(self._sVolume)

    def mute_changed(self, muted: bool) -> None:
        """Mute or unmute the player

        Parameters
        ----------
        muted : bool
            True to mute
        """
        player.muted = muted
        self._bMute.setIconName("mute" if muted else "volume")

    def device_changed(self, name: str) -> None:
        """Use the selected output device; a device which cannot play the signal is refused and the previous one kept

        Parameters
        ----------
        name : str
            The name of the device
        """
        index = self._devices[name]
        try:
            player.setDevice(index)
        except sd.PortAudioError as ex:
            QtWidgets.QMessageBox.warning(self, "Output device", f'The device "{name}" cannot be used:\n{ex}')
            self._boxDevices.blockSignals(True)
            self._boxDevices.setCurrentText(self._deviceName(player.device))
            self._boxDevices.blockSignals(False)

    def _deviceName(self, index: int | None) -> str:
        """Find the name of an output device

        Parameters
        ----------
        index : int or None
            The device index (None for the default output device)

        Returns
        -------
        str
            The name, or an empty string if the device is not in the list
        """
        if index is None:
            index = sd.default.device[1]
        for name, cur_index in self._devices.items():
            if cur_index == index:
                return name
        return ""

    def volume_changed(self) -> None:
        """Apply the volume of the slider to the player"""
        player.volume = self._sVolume.value() / 100


class ViewWidget(QtWidgets.QWidget):
    """View of the plots: zoom, following the playhead and the theme

    Parameters
    ----------
    wav_plot : pg.PlotWidget
        The waveform plot: the time axis of every other plot is linked to it
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    #: How much a click on a zoom button changes the visible duration
    ZOOM_FACTOR = 2.0

    #: The shortest visible duration, in seconds
    MIN_VISIBLE_DURATION = 0.01

    def __init__(self, wav_plot: Any, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._wav_plot = wav_plot

        self._bZoomOut = ToolBarButton("zoom_out", "Zoom out", "zoom_out")
        self._bZoomIn = ToolBarButton("zoom_in", "Zoom in", "zoom_in")
        self._bZoomFit = ToolBarButton("zoom_fit", "Show the whole signal", "zoom_fit")
        self._bFollow = ToolBarButton("follow", "Follow the playhead", "follow")
        self._bFollow.setCheckable(True)
        self._bFollow.setChecked(True)
        self._bTheme = ToolBarButton("theme", "Switch the theme", "switch_theme")
        self._bZoomOut.clicked.connect(lambda: self.zoom(self.ZOOM_FACTOR))
        self._bZoomIn.clicked.connect(lambda: self.zoom(1 / self.ZOOM_FACTOR))
        self._bZoomFit.clicked.connect(self.zoomFit)
        self._bTheme.clicked.connect(theme.toggle_theme)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        for button in (self._bZoomOut, self._bZoomIn, self._bZoomFit, self._bFollow):
            layout.addWidget(button)
        layout.addSpacing(12)
        layout.addWidget(self._bTheme)

        self._follow_timer = QtCore.QTimer(self)
        self._follow_timer.setInterval(30)
        self._follow_timer.timeout.connect(self.followPlayhead)
        self._follow_timer.start()

    def zoom(self, factor: float) -> None:
        """Change the visible duration, around the playhead if it is visible (around the middle otherwise)

        Parameters
        ----------
        factor : float
            By how much the visible duration is multiplied
        """
        x_min, x_max = self._wav_plot.getViewBox().viewRange()[0]
        duration = player.duration
        width = min(max((x_max - x_min) * factor, self.MIN_VISIBLE_DURATION), duration)
        centre = player.position if x_min <= player.position <= x_max else (x_min + x_max) / 2
        start = min(max(centre - width / 2, 0.0), duration - width)
        self._wav_plot.setXRange(start, start + width, padding=0)

    def zoomFit(self) -> None:
        """Show the whole signal"""
        self._wav_plot.setXRange(0, player.duration, padding=0)

    def followPlayhead(self) -> None:
        """During a playback, turn the page when the playhead leaves the view"""
        if not self._bFollow.isChecked() or not player.is_playing or player.is_paused:
            return
        x_min, x_max = self._wav_plot.getViewBox().viewRange()[0]
        position = player.position
        if not x_min <= position <= x_max:
            start = min(position, player.duration - (x_max - x_min))
            self._wav_plot.setXRange(start, start + (x_max - x_min), padding=0)


class ControlLayout(QtWidgets.QVBoxLayout):
    """Audio tab: current file (with the load button) and the equalizer

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        The parent widget
    """

    def __init__(self, parent: QtWidgets.QWidget | None) -> None:
        super().__init__(parent)

        # Create the main layout
        box_layout = QtWidgets.QVBoxLayout()
        box_layout.setContentsMargins(0, 0, 0, 0)
        box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Prepare scrollbar
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)

        # Generate the necessary widgets
        self._file_box = self._generate_file_box()
        self._eq_widget = ParametricEqWidget()

        # Add the widgets
        box_layout.addWidget(self._file_box)
        box_layout.addWidget(self._eq_widget)
        box_layout.addStretch(1)  # The groups only take the height they need, from the top

        # Generate Configuration Widget
        configuration_widget = QtWidgets.QWidget()
        configuration_widget.setLayout(box_layout)
        scroll.setWidget(configuration_widget)

        # Finalize the layout
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.addWidget(scroll)

    def _generate_file_box(self) -> QtWidgets.QGroupBox:
        """Create the box showing the current audio file, with the load and save buttons

        Returns
        -------
        QtWidgets.QGroupBox
            The box
        """
        file_box_layout = QtWidgets.QGridLayout()
        file_box_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        # Start time
        l1 = QtWidgets.QLabel("Current File")
        self._wCurrentFile = QtWidgets.QLineEdit("none")
        self._wCurrentFile.setEnabled(False)
        file_box_layout.addWidget(l1, 1, 0)
        file_box_layout.addWidget(self._wCurrentFile, 1, 1)

        self._bLoadFile = QtWidgets.QPushButton("Load File")
        self._bLoadFile.setEnabled(False)  # Enabled once a load handler is set (see setLoadHandler)
        self._bLoadFile.setDefault(False)
        self._bLoadFile.setAutoDefault(False)
        file_box_layout.addWidget(self._bLoadFile)

        self._bSaveFile = QtWidgets.QPushButton("Save File")
        self._bSaveFile.setEnabled(False)  # TODO: nothing modifies the signal yet, so there is nothing to save
        self._bSaveFile.setToolTip("Saving audio is not implemented yet")
        self._bSaveFile.setDefault(False)
        self._bSaveFile.setAutoDefault(False)
        file_box_layout.addWidget(self._bSaveFile)

        file_box = QtWidgets.QGroupBox("Audio File")
        file_box.setLayout(file_box_layout)

        return file_box

    def setLoadHandler(self, handler: Callable[[], None]) -> None:
        """Define the function called by the "Load File" button"""
        self._bLoadFile.clicked.connect(handler)
        self._bLoadFile.setEnabled(True)

    def setCurrentFile(self, filename: str) -> None:
        """Show the name of the current audio file

        Parameters
        ----------
        filename : str
            The file name
        """
        self._wCurrentFile.setText(filename)
        self._eq_widget.refresh()  # The sampling rate has probably changed


_controller = None


def get_controller() -> ControlLayout:
    """Return the audio control layout, creating it on first use (a QApplication must exist)

    The layout is also re-created if its Qt object has been deleted (e.g. when the window owning it was closed).
    """
    global _controller
    # NOTE: the layout wrapper can outlive the widgets it manages, so check one of them too
    if (_controller is None) or (not isQObjectAlive(_controller)) or (not isQObjectAlive(_controller._file_box)):
        _controller = ControlLayout(None)
    return _controller
