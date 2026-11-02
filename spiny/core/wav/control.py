# Python
from __future__ import annotations

from collections.abc import Callable
from typing import Any

# Python SoundDevice
import sounddevice as sd

# SpINY
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets, isQObjectAlive

from spiny.gui.icons import transport_icon

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

    #: The colour of the play button
    PLAY_COLOR = QtGui.QColor("#2fa66a")

    STYLE_SHEET = """
        QToolButton { border: none; border-radius: 6px; padding: 5px; }
        QToolButton:hover { background: rgba(127, 127, 127, 50); }
        QToolButton:pressed { background: rgba(127, 127, 127, 90); }
        QToolButton:checked { background: #2a78d6; }
        QToolButton:disabled { background: transparent; }
        QLabel#time { background: #17181a; color: #7fe3a8; border-radius: 6px; padding: 4px 10px; }
        QLabel#duration { background: #17181a; color: #7c8088; border-radius: 6px; padding: 4px 10px; }
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(self.STYLE_SHEET)
        icon_color = self.palette().color(QtGui.QPalette.ColorRole.ButtonText)

        self._play_icon = transport_icon("play", self.PLAY_COLOR)
        self._pause_icon = transport_icon("pause", self.PLAY_COLOR)
        self._bStart = self._transportButton(transport_icon("start", icon_color), "Return to start", "Home")
        self._bPlay = self._transportButton(self._play_icon, "Play / Pause", "Space")
        self._bStop = self._transportButton(transport_icon("stop", icon_color), "Stop", "Esc")
        self._bLoop = self._transportButton(transport_icon("loop", icon_color, QtGui.QColor("white")), "Loop", "L")
        self._bLoop.setCheckable(True)
        self._bLoop.setChecked(player.loop_activated)
        self._bStart.clicked.connect(lambda: player.seek(0.0))
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

        # Without any output device, playback controls are useless
        if not output_devices()[0]:
            for button in (self._bStart, self._bPlay, self._bStop, self._bLoop):
                button.setEnabled(False)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        for button in (self._bStart, self._bPlay, self._bStop, self._bLoop):
            layout.addWidget(button)
        layout.addSpacing(12)
        layout.addWidget(self._lTime)
        layout.addWidget(self._lDuration)

        self._refresh()
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(30)
        self._refresh_timer.timeout.connect(self._refresh)
        self._refresh_timer.start()

    def _transportButton(self, icon: QtGui.QIcon, tooltip: str, shortcut: str) -> QtWidgets.QToolButton:
        """Create a button of the transport

        Parameters
        ----------
        icon : QtGui.QIcon
            The icon
        tooltip : str
            What the button does
        shortcut : str
            The keyboard shortcut

        Returns
        -------
        QtWidgets.QToolButton
            The button
        """
        button = QtWidgets.QToolButton()
        button.setIcon(icon)
        button.setIconSize(QtCore.QSize(22, 22))
        button.setToolTip(f"{tooltip} ({shortcut})")
        button.setShortcut(QtGui.QKeySequence(shortcut))  # NOTE: typing in a text field still goes to the field
        button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        return button

    def _refresh(self) -> None:
        """Show the state of the player: position, duration and play or pause icon"""
        self._lTime.setText(format_time(player.position))
        self._lDuration.setText(format_time(player.duration))
        playing = player.is_playing and not player.is_paused
        self._bPlay.setIcon(self._pause_icon if playing else self._play_icon)

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

    STYLE_SHEET = """
        QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: rgba(127, 127, 127, 90); }
        QSlider::sub-page:horizontal { border-radius: 2px; background: #2a78d6; }
        QSlider::handle:horizontal {
            width: 12px; margin: -4px 0; border-radius: 6px; background: palette(button-text);
        }
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(self.STYLE_SHEET)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Preferred)
        icon_color = self.palette().color(QtGui.QPalette.ColorRole.ButtonText)

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
        volume_icon = QtWidgets.QLabel()
        volume_icon.setPixmap(transport_icon("volume", icon_color).pixmap(20, 20))
        self._sVolume = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._sVolume.setRange(0, 100)
        self._sVolume.setValue(round(player.volume * 100))
        self._sVolume.setFixedWidth(120)
        self._sVolume.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._sVolume.setToolTip("Volume")
        self._sVolume.valueChanged.connect(self.volume_changed)
        self._lVolume = QtWidgets.QLabel()
        self._lVolume.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._lVolume.setFixedWidth(40)
        self.volume_changed()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)
        layout.addWidget(self._boxDevices)
        layout.addSpacing(12)
        layout.addWidget(volume_icon)
        layout.addWidget(self._sVolume)
        layout.addWidget(self._lVolume)

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
        self._lVolume.setText(f"{self._sVolume.value()}%")


class ControlLayout(QtWidgets.QVBoxLayout):
    """Audio tab: current file (with the load button) and the equalizer place holder

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
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidgetResizable(True)

        # Generate the necessary widgets
        self._file_box = self._generate_file_box()
        self._eq_widget = EqWidget(None, (9, 1))  # NOTE: place holder, the equalizer is not implemented yet
        self._eq_widget.setEnabled(False)
        self._eq_widget.setToolTip("The equalizer is not implemented yet")

        # Add the widgets
        box_layout.addWidget(self._file_box)
        box_layout.addWidget(self._eq_widget)

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


class EqWidget(QtWidgets.QGroupBox):
    """Equalizer (place holder: the sliders are shown but not applied yet)

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        The parent widget
    wav : tuple(Any, Any)
        The (signal, sampling rate) to equalize (unused for now)
    """

    def __init__(self, parent: QtWidgets.QWidget | None, wav: tuple[Any, Any]) -> None:
        super().__init__(title="Equalizer", parent=parent)

        self._signal = wav[0]
        self._sampling_rate = wav[1]

        slider_layout = self._define_sliders()
        self._apply_button = QtWidgets.QPushButton("Apply")
        overall_layout = QtWidgets.QVBoxLayout()
        overall_layout.addLayout(slider_layout)
        overall_layout.addWidget(self._apply_button)
        self.setLayout(overall_layout)

    def _define_sliders(self) -> QtWidgets.QHBoxLayout:
        """Create one slider per frequency band

        Returns
        -------
        QtWidgets.QHBoxLayout
            The layout of the sliders
        """

        self._frequencies = [50, 200, 1000, 2000, 4000, 8000, 16000]

        layout = QtWidgets.QHBoxLayout()

        prev_freq = 0
        for freq in self._frequencies:

            cur_slider = EqSlider(prev_freq, freq, self)
            layout.addWidget(cur_slider)
            prev_freq = freq

        return layout


class EqSlider(QtWidgets.QWidget):
    """Vertical gain slider (-120 to 0 dB) of one equalizer band

    Parameters
    ----------
    lower_freq : float
        The lower bound of the band, in Hz
    upper_freq : float
        The upper bound of the band, in Hz
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    def __init__(self, lower_freq: float, upper_freq: float, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self._verticalLayout = QtWidgets.QVBoxLayout(self)
        self._label = QtWidgets.QLabel(self)
        self._verticalLayout.addWidget(self._label)
        self._horizontalLayout = QtWidgets.QHBoxLayout()
        spacerItem = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._horizontalLayout.addItem(spacerItem)
        self._slider = QtWidgets.QSlider(self)
        self._slider.setOrientation(QtCore.Qt.Vertical)
        self._horizontalLayout.addWidget(self._slider)
        spacerItem1 = QtWidgets.QSpacerItem(0, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self._horizontalLayout.addItem(spacerItem1)
        self._verticalLayout.addLayout(self._horizontalLayout)
        self.resize(self.sizeHint())

        self._slider.setMinimum(-120)
        self._slider.setMaximum(0)
        self._slider.setValue(0)
        self._slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self._slider.setTickInterval(10)  # one tick every 10 dB

        self._lower_freq = lower_freq
        self._upper_freq = upper_freq

        self.setLabelValue(upper_freq)

    def setLabelValue(self, upper_freq: float) -> None:
        """Show the upper bound of the band (in kHz above 1 kHz)

        Parameters
        ----------
        upper_freq : float
            The upper bound, in Hz
        """
        if upper_freq >= 1000:
            self._label.setText(f"< {int(upper_freq/1000):2d}k")
        else:
            self._label.setText(f"< {upper_freq}")


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
