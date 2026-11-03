from __future__ import annotations

import os
from typing import Any

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtWidgets

from spiny.core import player
from spiny.core.overlay import ColorSwatch, Overlay, register_overlay
from spiny.gui import theme
from spiny.gui.helpers.widgets import LabelledSlider

from .extractor import load_mask, mask_image


class MaskOverlay(Overlay):
    """A transparency mask read from a numpy file, whose coefficients are the opacity of what is below

    Hiding the plot with its background colour, by an image above it, looks like making it transparent. The image only
    has the resolution of the screen, and only covers the view and a margin: it is cheap to update, whatever the size
    of the mask.
    """

    def __init__(self) -> None:
        super().__init__("Mask")
        self._file_mask: Any = None  # As in the file
        self.filename: Any = None
        self._drawn: tuple[int, int, int] | None = None  # What the image shows: (first frame, last frame, stride)
        self._setDefaults()

    def _setDefaults(self) -> None:
        """Set the configuration to its default values"""
        self.swap_axes = False
        self.invert = False
        self.strength = 1.0
        self.frame_shift = 0.0  # In milliseconds, 0 for a mask which spans the whole signal
        self.max_frequency = 0.0  # In Hz, 0 for half of the sampling rate
        self._color: QtGui.QColor | None = None  # None for the background of the plot

    def resetConfiguration(self) -> None:
        """Go back to the default configuration: the mask stays loaded"""
        self._setDefaults()
        self._changed()

    ###########################################################################
    # The mask
    ###########################################################################

    def loadMask(self, filename: str | os.PathLike) -> None:
        """Use the mask of a file

        Parameters
        ----------
        filename : str or pathlib.Path
            The numpy file

        Raises
        ------
        ValueError
            if the file does not contain a mask: the current one is kept
        OSError
            if the file cannot be read: the current one is kept
        """
        self._file_mask = load_mask(filename)
        self.filename = filename
        self._changed()

    @property
    def mask(self) -> Any:
        """np.ndarray or None: The opacities, shape (nb_frames, nb_bins), None if no mask is loaded"""
        if self._file_mask is None:
            return None
        return self._file_mask.T if self.swap_axes else self._file_mask

    def color(self, name: str = "") -> QtGui.QColor:
        """Give what is seen where the opacity is 0

        Parameters
        ----------
        name : str, optional
            Unused: the mask only has one colour

        Returns
        -------
        QtGui.QColor
            The colour
        """
        return self._color if self._color is not None else theme.color("plot_background")

    def setColor(self, name: str, color: QtGui.QColor) -> None:
        """Change what is seen where the opacity is 0

        Parameters
        ----------
        name : str
            Unused: the mask only has one colour
        color : QtGui.QColor
            The colour
        """
        self._color = color
        self._changed()

    def setConfiguration(self, **changes: Any) -> None:
        """Change settings of the mask

        Parameters
        ----------
        changes : keyword arguments
            The attributes to change (swap_axes, invert, strength, frame_shift or max_frequency)
        """
        for name, value in changes.items():
            setattr(self, name, value)
        self._changed()

    def applyTheme(self) -> None:
        """Follow the theme: the default colour is the background of the plot"""
        self._changed()

    def _changed(self) -> None:
        """Draw again"""
        self._drawn = None
        self._update()

    ###########################################################################
    # Drawing
    ###########################################################################

    def _createItems(self) -> list[Any]:
        """Create the image

        Returns
        -------
        list(pg.ImageItem)
            The image
        """
        image = pg.ImageItem(axisOrder="col-major")
        image.setZValue(3)  # NOTE: above the plot, below the tracks of the other overlays and the playhead
        self._drawn = None
        return [image]

    @property
    def _image(self) -> Any:
        """pg.ImageItem or None: The image, if the overlay is on a plot"""
        return self._items[0] if self._items else None

    def _update(self) -> None:
        """Show or hide the image"""
        if self._image is None:
            return
        active = self.is_active and self.mask is not None
        self._image.setVisible(active)
        if active:
            self._draw()

    def _onViewChanged(self, *args: Any) -> None:
        """Follow the view

        Parameters
        ----------
        args : list
            The arguments of the signal (unused)
        """
        if self.is_active and self.mask is not None:
            self._draw()

    def frameDuration(self) -> float:
        """Give the duration of a frame of the mask

        Returns
        -------
        float
            The duration, in seconds
        """
        if self.frame_shift > 0:
            return self.frame_shift / 1000.0
        return player.duration / max(self.mask.shape[0], 1)

    def _draw(self) -> None:
        """Give the image the part of the mask around the view, unless it already has it"""
        mask = self.mask
        frame_duration = self.frameDuration()
        if frame_duration <= 0:
            return

        start, end = self._visibleRange()
        first = int(start / frame_duration)
        last = min(int(np.ceil(end / frame_duration)) + 1, mask.shape[0])
        view = self._plot.getViewBox()
        stride = max((last - first) // max(int(view.width()), 1), 1)
        if self._drawn is not None:
            drawn_first, drawn_last, drawn_stride = self._drawn
            at_the_end = drawn_last >= mask.shape[0]
            if drawn_first <= first and (last <= drawn_last or at_the_end) and drawn_stride == stride:
                return

        # NOTE: half a view more on each side, so that small pans do not need any drawing
        margin = (last - first) // 2
        first = max(first - margin, 0) // stride * stride
        last = min(last + margin, mask.shape[0])
        self._drawn = (first, last, stride)
        if last <= first:
            self._image.setVisible(False)
            return
        self._image.setVisible(True)

        top = self.max_frequency if self.max_frequency > 0 else player.sampling_rate / 2
        visible_bins = mask.shape[1] * (view.viewRange()[1][1] - view.viewRange()[1][0]) / top
        bin_stride = max(int(visible_bins / max(view.height(), 1)), 1)
        color = self.color()
        image = mask_image(
            mask,
            first,
            last,
            stride,
            bin_stride,
            (color.red(), color.green(), color.blue()),
            self.strength,
            self.invert,
        )
        self._image.setImage(image, autoLevels=False)

        transform = QtGui.QTransform.fromTranslate(first * frame_duration, 0.0)
        transform.scale(stride * frame_duration, bin_stride * top / mask.shape[1])  # applied before the translation
        self._image.setTransform(transform)

    ###########################################################################
    # Control panel
    ###########################################################################

    def buildPanel(self) -> QtWidgets.QWidget:
        """Create the configuration panel: the file, and how the mask is applied

        Returns
        -------
        QtWidgets.QWidget
            The panel
        """
        self._lFile = QtWidgets.QLabel()
        self._lFile.setWordWrap(True)
        load = QtWidgets.QPushButton("Load a mask...")
        load.setToolTip("A numpy file (.npy): a matrix of opacities between 0 and 1")
        load.setAutoDefault(False)
        load.clicked.connect(self._askFile)
        self._showFile()

        file_layout = QtWidgets.QVBoxLayout()
        file_layout.addWidget(self._lFile)
        file_layout.addWidget(load)
        file_box = QtWidgets.QGroupBox("File")
        file_box.setLayout(file_layout)

        swap = QtWidgets.QCheckBox("The rows of the file are the frequency bins")
        swap.setToolTip("By default, the rows are the frames and the columns are the frequency bins")
        swap.setChecked(self.swap_axes)
        swap.toggled.connect(self._onSwap)
        frame_shift = QtWidgets.QDoubleSpinBox()
        frame_shift.setRange(0.0, 1000.0)
        frame_shift.setSuffix(" ms")
        frame_shift.setSpecialValueText("Spans the whole signal")
        frame_shift.setValue(self.frame_shift)
        frame_shift.valueChanged.connect(lambda value: self.setConfiguration(frame_shift=value))
        max_frequency = QtWidgets.QSpinBox()
        max_frequency.setRange(0, 192000)
        max_frequency.setSingleStep(100)
        max_frequency.setSuffix(" Hz")
        max_frequency.setSpecialValueText("Half of the sampling rate")
        max_frequency.setValue(round(self.max_frequency))
        max_frequency.valueChanged.connect(lambda value: self.setConfiguration(max_frequency=float(value)))

        layout_form = QtWidgets.QFormLayout()
        layout_form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)  # wider controls
        layout_form.addRow(swap)
        layout_form.addRow("Time between two frames", frame_shift)
        layout_form.addRow("Frequency of the last bin", max_frequency)
        layout_box = QtWidgets.QGroupBox("Layout of the mask")
        layout_box.setLayout(layout_form)

        invert = QtWidgets.QCheckBox("Invert: 1 hides and 0 shows")
        invert.setChecked(self.invert)
        invert.toggled.connect(lambda checked: self.setConfiguration(invert=checked))
        strength = LabelledSlider(0, 100, round(self.strength * 100), lambda v: f"{v} %")
        strength.valueChanged.connect(lambda value: self.setConfiguration(strength=value / 100))
        display_form = QtWidgets.QFormLayout()
        display_form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapAllRows)
        display_form.addRow(invert)
        display_form.addRow("Strength", strength)
        display_form.addRow("Colour of what is hidden", ColorSwatch(self, "the hidden parts"))
        display_box = QtWidgets.QGroupBox("Display")
        display_box.setLayout(display_form)

        panel = QtWidgets.QGroupBox("Mask")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.addWidget(file_box)
        layout.addWidget(layout_box)
        layout.addWidget(display_box)
        return panel

    def _showFile(self) -> None:
        """Show which mask is loaded"""
        if self.mask is None:
            self._lFile.setText("No mask is loaded.")
        else:
            nb_frames, nb_bins = self.mask.shape
            self._lFile.setText(f"{os.path.basename(self.filename)}: {nb_frames} frames × {nb_bins} frequency bins")

    def _askFile(self) -> None:
        """Ask for a mask and load it (errors are shown in a message box)"""
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self._lFile, "Load a mask", "", "Numpy files (*.npy);;All Files (*)", options=options
        )
        if not filename:  # Cancelled
            return
        try:
            self.loadMask(filename)
        except (OSError, ValueError) as ex:
            QtWidgets.QMessageBox.critical(self._lFile, "Load a mask", f"Cannot load the mask:\n{ex}")
            return
        self._showFile()

    def _onSwap(self, checked: bool) -> None:
        """Change which dimension of the file is the time

        Parameters
        ----------
        checked : bool
            True if the rows of the file are the frequency bins
        """
        self.setConfiguration(swap_axes=checked)
        self._showFile()


overlay = MaskOverlay()
register_overlay(overlay)

__all__ = ["MaskOverlay", "load_mask", "mask_image", "overlay"]
