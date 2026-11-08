from __future__ import annotations

import re
from collections.abc import Callable

from pyqtgraph.Qt.QtCore import QAbstractItemModel, QSortFilterProxyModel, Qt, Signal
from pyqtgraph.Qt.QtWidgets import QComboBox, QCompleter, QHBoxLayout, QLineEdit, QListWidget, QSlider, QWidget


class CompactList(QListWidget):
    """List only as high as its entries, between `MIN_VISIBLE_ROWS` and `MAX_VISIBLE_ROWS` (it scrolls above)"""

    MIN_VISIBLE_ROWS = 1
    MAX_VISIBLE_ROWS = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model().rowsInserted.connect(self._fitToRows)
        self.model().rowsRemoved.connect(self._fitToRows)
        self.model().modelReset.connect(self._fitToRows)
        self._fitToRows()

    def _fitToRows(self) -> None:
        """Take the height of the entries"""
        row_height = self.sizeHintForRow(0) if self.count() else self.fontMetrics().height()
        nb_rows = min(max(self.count(), self.MIN_VISIBLE_ROWS), self.MAX_VISIBLE_ROWS)
        self.setFixedHeight(nb_rows * row_height + 2 * self.frameWidth())


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


#: A number in the text of a value: its unit can be anything, only a "k" (as in "2 kHz" or "2k") changes the value
_NUMBER = re.compile(r"([-+]?(?:\d+[.,]?\d*|[.,]\d+))\s*(k?)", re.IGNORECASE)


class LabelledSlider(QWidget):
    """Horizontal slider with its current value next to it, in a field which can be edited

    The value typed in the field is applied when the edition ends (Enter, or leaving the field), not at each key: a
    change can start an analysis. A text which is not a number puts the current value back.

    Parameters
    ----------
    minimum : int
        The smallest value
    maximum : int
        The largest value
    value : int
        The initial value
    formatter : callable, optional
        Converts a value into the text of the field. (default: str)
    step : int, optional
        The change made by the arrow keys (ten times more with Page Up/Down). (default: 1)
    parent : QWidget, optional
        The parent widget. (default: None)
    to_value : callable, optional
        Converts the number typed in the field into a value of the slider, when the text is not the value itself
        (default: None, i.e. the number rounded)
    compact : bool, optional
        For a toolbar: a narrow field, and a slider which does not take the focus of the keyboard. (default: False)
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
        to_value: Callable[[float], int] = round,
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        self._formatter = formatter
        self._to_value = to_value

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(minimum, maximum)
        self._slider.setSingleStep(step)
        self._slider.setPageStep(10 * step)
        self._slider.setValue(value)
        self._field = QLineEdit(formatter(value))
        widest = max(self._field.fontMetrics().horizontalAdvance(formatter(v)) for v in (minimum, value, maximum))
        self._field.setFixedWidth(widest + 16 if compact else max(widest + 16, 110))  # So that the slider does not move
        if compact:
            self._slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._field)
        self._slider.valueChanged.connect(self._onValueChanged)
        self._field.editingFinished.connect(self._onFieldEdited)
        # NOTE: Enter gives the keyboard back to the application: Space plays again, and does not edit the field
        self._field.returnPressed.connect(self._field.clearFocus)

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
        self._field.setText(self._formatter(value))
        self.valueChanged.emit(value)

    def _onFieldEdited(self) -> None:
        """Apply the number typed in the field (the text is then rewritten in the format of the slider)"""
        match = _NUMBER.search(self._field.text())
        if match is not None:
            number = float(match.group(1).replace(",", "."))
            self._slider.setValue(self._to_value(number * 1000 if match.group(2) else number))
        self._field.setText(self._formatter(self._slider.value()))
