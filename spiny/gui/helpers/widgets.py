from __future__ import annotations

from pyqtgraph.Qt.QtCore import QAbstractItemModel, QSortFilterProxyModel, Qt
from pyqtgraph.Qt.QtWidgets import QComboBox, QCompleter, QWidget


class ExtendedComboBox(QComboBox):
    """An extended combox which provides to filter items by filling text

    The original code is coming from https://stackoverflow.com/a/50639066
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super(ExtendedComboBox, self).__init__(parent)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setEditable(True)

        # add a filter model to filter matching items
        self.pFilterModel = QSortFilterProxyModel(self)
        self.pFilterModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.pFilterModel.setSourceModel(self.model())

        # add a completer, which uses the filter model
        # NOTE: not named "completer" to avoid shadowing QComboBox.completer()
        self._completer = QCompleter(self.pFilterModel, self)
        # always show all (filtered) completions
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setCompleter(self._completer)

        # connect signals
        self.lineEdit().textEdited.connect(self.pFilterModel.setFilterFixedString)
        self._completer.activated.connect(self.on_completer_activated)

    # on selection of an item from the completer, select the corresponding item from combobox
    def on_completer_activated(self, text: str) -> None:
        """Select the entry chosen in the completer popup

        Parameters
        ----------
        text : str
            The chosen entry
        """
        if text:
            index = self.findText(text)
            self.setCurrentIndex(index)
            # NOTE: Qt6 removed the activated(QString) overload, textActivated is its replacement
            self.textActivated.emit(self.itemText(index))

    # on model change, update the models of the filter and completer as well
    def setModel(self, model: QAbstractItemModel) -> None:
        """Use a new model, also for the filter and the completer

        Parameters
        ----------
        model : QAbstractItemModel
            The model
        """
        super(ExtendedComboBox, self).setModel(model)
        self.pFilterModel.setSourceModel(model)
        self._completer.setModel(self.pFilterModel)

    # on model column change, update the model column of the filter and completer as well
    def setModelColumn(self, column: int) -> None:
        """Use another column of the model, also for the filter and the completer

        Parameters
        ----------
        column : int
            The column
        """
        self._completer.setCompletionColumn(column)
        self.pFilterModel.setFilterKeyColumn(column)
        super(ExtendedComboBox, self).setModelColumn(column)
