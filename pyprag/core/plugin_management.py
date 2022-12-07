from pyqtgraph.dockarea import Dock


class DataController:
    def __init__(self):
        pass

    def extract(self):
        self._extractor.extract()
        self._widget.refresh()

    def refresh(self):
        self._widget.refresh()
        self._widget.setXLink(self._wav_plot)


class DataDock(Dock):
    def __init__(self, widget, name, size):
        Dock.__init__(self, name=name, size=size)

        # Override the label
        self.label.sigClicked.connect(self.mouseClicked)
        self._data_plot = None

        self.setWidget(widget)

    def dropWidget(self, widget):
        """
        Add a new widget to the interior of this Dock.
        Each Dock uses a QGridLayout to arrange widgets within.
        """
        self.currentRow = self.currentRow - 1
        self.widgets.remove(widget)
        self.layout.removeWidget(widget)
        self.dockdrop.raiseOverlay()

    def setWidget(self, widget):
        # Ensure widgets are removed
        if self._data_plot is not None:
            self.removeWidget(self._data_plot)

        # Now define new one
        self._data_plot = widget
        self._data_plot.hideAxis("bottom")
        self._data_plot.getAxis("left").setWidth(50)

        # Add plot
        # self.data_plot.disableAutoRange()
        self.addWidget(self._data_plot)

    def mouseClicked(self):
        pass


plugin_entry_list = []
