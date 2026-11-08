from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
from pyqtgraph.Qt import QtWidgets

from spiny.core.overlay import TrackOverlay, register_overlay, track_display_box
from spiny.gui.helpers.widgets import LabelledSlider

from .extractor import F0Settings, compute_f0


class F0Overlay(TrackOverlay):
    """The F0, drawn over a spectrogram"""

    TRACKS = ("F0",)

    def __init__(self) -> None:
        super().__init__("F0", F0Settings())

    def compute(
        self, signal: np.ndarray, rate: int, settings: F0Settings, first_frame: int, last_frame: int
    ) -> np.ndarray:
        """Compute the F0 of some frames, see TrackOverlay.compute"""
        return compute_f0(signal, rate, settings, first_frame, last_frame)

    def buildPanel(self) -> QtWidgets.QWidget:
        """Create the configuration panel: what is shown, and the parameters of the analysis

        Returns
        -------
        QtWidgets.QWidget
            The panel
        """
        settings = self.settings
        self._min_f0 = LabelledSlider(30, 400, round(settings.min_f0), lambda v: f"{v} Hz", step=5)
        self._max_f0 = LabelledSlider(100, 1000, round(settings.max_f0), lambda v: f"{v} Hz", step=10)
        self._min_f0.valueChanged.connect(self._onMinF0)
        self._max_f0.valueChanged.connect(self._onMaxF0)
        voicing = LabelledSlider(
            0,
            100,
            round(settings.voicing_threshold * 100),
            lambda v: f"{v / 100:.2f}",
            to_value=lambda t: round(t * 100),
        )
        voicing.valueChanged.connect(lambda value: self._changeSettings(voicing_threshold=value / 100))
        silence = LabelledSlider(0, 30, round(settings.silence_threshold * 100), lambda v: f"{v} %")
        silence.valueChanged.connect(lambda value: self._changeSettings(silence_threshold=value / 100))
        time_step = LabelledSlider(1, 20, round(settings.time_step), lambda v: f"{v} ms")
        time_step.valueChanged.connect(lambda value: self._changeSettings(time_step=value))

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)  # wider sliders
        form.addRow("Minimum F0", self._min_f0)
        form.addRow("Maximum F0", self._max_f0)
        form.addRow("Voicing threshold", voicing)
        form.addRow("Silence below the peak", silence)
        form.addRow("Time step", time_step)
        analysis = QtWidgets.QGroupBox("Analysis")
        analysis.setLayout(form)

        panel = QtWidgets.QGroupBox("F0")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.addWidget(track_display_box(self, self.TRACKS))
        layout.addWidget(analysis)
        return panel

    def _onMinF0(self, value: int) -> None:
        """Change the minimum F0, pushing the maximum so that the range stays valid

        Parameters
        ----------
        value : int
            The minimum F0, in Hz
        """
        if value >= self._max_f0.value():
            self._max_f0.setValue(value + 10)
        self._changeSettings(min_f0=value)

    def _onMaxF0(self, value: int) -> None:
        """Change the maximum F0, pushing the minimum so that the range stays valid

        Parameters
        ----------
        value : int
            The maximum F0, in Hz
        """
        if value <= self._min_f0.value():
            self._min_f0.setValue(value - 10)
        self._changeSettings(max_f0=value)

    def _changeSettings(self, **changes: Any) -> None:
        """Change parameters of the analysis

        Parameters
        ----------
        changes : keyword arguments
            The parameters to change
        """
        self.setSettings(dataclasses.replace(self.settings, **changes))


overlay = F0Overlay()
register_overlay(overlay)

__all__ = ["F0Settings", "F0Overlay", "compute_f0", "overlay"]
