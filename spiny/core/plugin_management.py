from pyqtgraph.dockarea import Dock


class DataController:
    def __init__(self):
        pass

    def extract(self):
        self._extractor.extract()
        self.refresh()

    def refresh(self):
        self._widget.refresh()
        self._widget.setXLink(self._wav_plot)


class DataDock(Dock):
    def __init__(self, size):
        Dock.__init__(self, name="Place Hold", size=size)

        # Override the label
        self.label.sigClicked.connect(self.mouseClicked)
        self._data_plot = None

    def removeWidget(self, widget):
        """
        Add a new widget to the interior of this Dock.
        Each Dock uses a QGridLayout to arrange widgets within.
        """
        self.widgets.remove(widget)
        i = self.layout.count() - 1
        cur_widget = self.layout.itemAt(i).widget()
        if cur_widget is not None:
            cur_widget.setParent(None)
        self.currentRow = self.currentRow - 1

    def setWidget(self, widget, name):
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

        # Update the name
        self.setTitle(name)

    def mouseClicked(self):
        pass


plugin_entry_dict = dict()
