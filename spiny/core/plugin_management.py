from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets

from pyqtgraph.dockarea import Dock


class DataController:
    """Controller of a data plugin: links an extractor (computes the data) and a widget (renders it)

    A plugin which needs no configuration can use this class directly; subclasses add a control panel
    (setControlPanel) or copy its values to the extractor before extracting (extract).

    Parameters
    ----------
    name : str
        The name of the plugin, as displayed in the plugin list
    extractor : Any
        The object computing the data (it provides extract() and optionally release())
    widget : Any
        The widget rendering the data (a spiny.gui.widgets.DataWidget)
    """

    _wav_plot: pg.PlotWidget

    def __init__(self, name: str, extractor: Any, widget: Any) -> None:
        self._name = name
        self._extractor = extractor
        self._widget = widget

    @property
    def name(self) -> str:
        """str: The name of the plugin (as displayed in the plugin list)"""
        return self._name

    @property
    def widget(self) -> QtWidgets.QWidget:
        """QtWidgets.QWidget: The widget rendering the data of the plugin"""
        return self._widget

    def setWavPlot(self, wav_plot: pg.PlotWidget) -> None:
        """Define the waveform plot the data plot is linked to (x axis)

        Parameters
        ----------
        wav_plot : pg.PlotWidget
            The waveform plot
        """
        self._wav_plot = wav_plot

    def setControlPanel(self, panel: QtWidgets.QLayout) -> None:
        """Add the control panel of the plugin (subclasses add their own configuration widgets)

        Parameters
        ----------
        panel : QtWidgets.QLayout
            The layout receiving the panel
        """
        panel.addWidget(QtWidgets.QWidget())

    def extract(self) -> None:
        """Extract the data from the loaded signal and refresh the rendering"""
        self._extractor.extract()
        self.refresh()

    def refresh(self) -> None:
        """Refresh the rendering and link its time axis to the waveform"""
        self._widget.refresh()
        self._widget.setXLink(self._wav_plot)

    def release(self) -> None:
        """Free the data of the plugin, called when another plugin is selected

        The data is extracted again when the plugin is selected again, so keeping it would only
        waste memory. The widget and the extractor take part if they provide `clearImageData`
        and `release` respectively.
        """
        clear = getattr(self._widget, "clearImageData", None)
        if clear is not None:
            clear()
        release = getattr(self._extractor, "release", None)
        if release is not None:
            release()


class DataDock(Dock):
    """Dock hosting the widget of the selected data plugin

    Parameters
    ----------
    size : tuple(int, int)
        The default size of the dock
    """

    currentRow: int  # NOTE: defined by pg.Dock

    def __init__(self, size: tuple[int, int]) -> None:
        Dock.__init__(self, name="Place Hold", size=size)

        self._data_plot: Any = None

    def removeWidget(self, widget: QtWidgets.QWidget) -> None:
        """Remove a widget from the dock (it is detached, not destroyed, so it can be shown again)

        Parameters
        ----------
        widget : QtWidgets.QWidget
            The widget to remove
        """
        self.widgets.remove(widget)
        i = self.layout.count() - 1
        cur_widget = self.layout.itemAt(i).widget()
        if cur_widget is not None:
            cur_widget.setParent(None)
        self.currentRow = self.currentRow - 1

    def setWidget(self, widget: QtWidgets.QWidget, name: str) -> None:
        """Replace the displayed data widget

        Parameters
        ----------
        widget : QtWidgets.QWidget
            The data widget (a DataWidget or a pg.PlotWidget)
        name : str
            The title of the dock
        """
        # Ensure widgets are removed
        if self._data_plot is not None:
            self.removeWidget(self._data_plot)

        # Now define new one
        self._data_plot = widget
        self._data_plot.hideAxis("bottom")
        self._data_plot.getAxis("left").setWidth(50)

        # Add plot
        self.addWidget(self._data_plot)

        # Update the name
        self.setTitle(name)


plugin_entry_dict: dict[str, DataController] = dict()


def register_plugin(controller: DataController) -> None:
    """Register a data plugin controller under its name

    Raises
    ------
    ValueError
        if a plugin with the same name is already registered
    """
    if controller.name in plugin_entry_dict:
        raise ValueError(f'A plugin named "{controller.name}" is already registered')
    plugin_entry_dict[controller.name] = controller
