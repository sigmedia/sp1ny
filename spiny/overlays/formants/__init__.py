from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
from pyqtgraph.Qt import QtWidgets

from spiny.core.overlay import TrackOverlay, register_overlay, track_display_box
from spiny.gui.helpers.widgets import LabelledSlider

from .extractor import FormantSettings, compute_formants


class FormantOverlay(TrackOverlay):
    """The formants, drawn over a spectrogram"""

    TRACKS = ("F1", "F2", "F3", "F4", "F5")

    def __init__(self) -> None:
        super().__init__("Formants", FormantSettings())
        self._shown["F4"] = self._shown["F5"] = False

    def compute(
        self, signal: np.ndarray, rate: int, settings: FormantSettings, first_frame: int, last_frame: int
    ) -> np.ndarray:
        """Compute the formants of some frames, see TrackOverlay.compute"""
        return compute_formants(signal, rate, settings, first_frame, last_frame)

    def buildPanel(self) -> QtWidgets.QWidget:
        """Create the configuration panel: what is shown, and the parameters of the analysis

        Returns
        -------
        QtWidgets.QWidget
            The panel
        """
        settings = self.settings

        def slider(field: str, minimum: int, maximum: int, text: str, step: int = 1) -> LabelledSlider:
            widget = LabelledSlider(minimum, maximum, round(getattr(settings, field)), lambda v: text.format(v), step)
            widget.valueChanged.connect(lambda value: self._changeSettings(**{field: value}))
            return widget

        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)  # wider sliders
        form.addRow("Maximum frequency", slider("max_frequency", 3000, 8000, "{} Hz", step=100))
        form.addRow("Number of formants", slider("nb_formants", 3, len(self.TRACKS), "{}"))
        form.addRow("Window length", slider("window_length", 10, 50, "{} ms"))
        form.addRow("Time step", slider("time_step", 1, 20, "{} ms"))
        form.addRow("Silence below the peak", slider("silence_db", 10, 80, "{} dB"))
        form.addRow("Maximum bandwidth", slider("max_bandwidth", 100, 1500, "{} Hz", step=50))
        analysis = QtWidgets.QGroupBox("Analysis")
        analysis.setLayout(form)

        panel = QtWidgets.QGroupBox("Formants")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.addWidget(track_display_box(self, self.TRACKS))
        layout.addWidget(analysis)
        return panel

    def _changeSettings(self, **changes: Any) -> None:
        """Change parameters of the analysis

        Parameters
        ----------
        changes : keyword arguments
            The parameters to change
        """
        self.setSettings(dataclasses.replace(self.settings, **changes))


overlay = FormantOverlay()
register_overlay(overlay)

__all__ = ["FormantSettings", "FormantOverlay", "compute_formants", "overlay"]
