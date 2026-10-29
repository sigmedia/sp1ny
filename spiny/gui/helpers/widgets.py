from __future__ import annotations

from collections.abc import Callable

from pyqtgraph.Qt.QtCore import QAbstractItemModel, QSortFilterProxyModel, Qt, Signal
from pyqtgraph.Qt.QtWidgets import QComboBox, QCompleter, QHBoxLayout, QLabel, QSlider, QWidget


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


class LabelledSlider(QWidget):
    """Horizontal slider showing its current value next to it

    Parameters
    ----------
    minimum : int
        The smallest value
    maximum : int
        The largest value
    value : int
        The initial value
    formatter : callable, optional
        Converts a value into the text of the label. (default: str)
    step : int, optional
        The change made by the arrow keys (ten times more with Page Up/Down). (default: 1)
    parent : QWidget, optional
        The parent widget. (default: None)
    """

    #: Emitted with the new value every time it changes (also while dragging)
    valueChanged = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        formatter: Callable[[int], str] = str,
        step: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._formatter = formatter

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(minimum, maximum)
        self._slider.setSingleStep(step)
        self._slider.setPageStep(10 * step)
        self._slider.setValue(value)
        self._label = QLabel(formatter(value))
        self._label.setMinimumWidth(110)  # room for the longest text, so that the slider does not move

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._label)
        self._slider.valueChanged.connect(self._onValueChanged)

    def value(self) -> int:
        """Return the current value

        Returns
        -------
        int
            The value
        """
        return self._slider.value()

    def setValue(self, value: int) -> None:
        """Change the value (valueChanged is emitted if it changes)

        Parameters
        ----------
        value : int
            The new value (clipped to the range of the slider)
        """
        self._slider.setValue(value)

    def _onValueChanged(self, value: int) -> None:
        """Update the label and forward the new value

        Parameters
        ----------
        value : int
            The new value
        """
        self._label.setText(self._formatter(value))
        self.valueChanged.emit(value)
