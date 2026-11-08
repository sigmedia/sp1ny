"""The dialog showing every keyboard shortcut of the application and allowing to change them"""

from __future__ import annotations

import yaml
from pyqtgraph.Qt import QtWidgets

from spiny.config import save_shortcuts
from spiny.gui.shortcuts import DEFAULT_SHORTCUTS, SHORTCUTS, duplicated_keys, set_shortcuts


class ShortcutsDialog(QtWidgets.QDialog):
    """A table of the actions and their shortcuts: the changes are applied at once and kept in the configuration file

    Parameters
    ----------
    parent : QtWidgets.QWidget, optional
        The parent widget. (default: None)
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")
        self.resize(480, 620)

        self._table = QtWidgets.QTableWidget(len(SHORTCUTS), 2)
        self._table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        self._table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)

        self._editors: dict[str, QtWidgets.QKeySequenceEdit] = {}
        for row, (action, key) in enumerate(SHORTCUTS.items()):
            self._table.setItem(row, 0, QtWidgets.QTableWidgetItem(action.replace("_", " ").capitalize()))
            editor = QtWidgets.QKeySequenceEdit(key)
            editor.setMaximumSequenceLength(1)
            editor.setClearButtonEnabled(True)
            self._table.setCellWidget(row, 1, editor)
            self._editors[action] = editor

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
            | QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self._restoreDefaults)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(buttons)

    def _restoreDefaults(self) -> None:
        """Show the default shortcuts (they are applied if the dialog is accepted)"""
        for action, editor in self._editors.items():
            editor.setKeySequence(DEFAULT_SHORTCUTS[action])

    def accept(self) -> None:
        """Apply and save the shortcuts, unless two actions have the same one: Qt would trigger neither of them"""
        shortcuts = {action: editor.keySequence().toString() for action, editor in self._editors.items()}
        duplicates = duplicated_keys(shortcuts)
        if duplicates:
            lines = [f"{key}: {', '.join(actions)}" for key, actions in duplicates.items()]
            message = "Several actions have the same shortcut:\n" + "\n".join(lines)
            QtWidgets.QMessageBox.warning(self, "Keyboard shortcuts", message)
            return

        set_shortcuts(shortcuts)
        try:
            save_shortcuts()
        except (OSError, yaml.YAMLError) as ex:
            message = f"The shortcuts are applied, but cannot be saved in the configuration file:\n{ex}"
            QtWidgets.QMessageBox.warning(self, "Keyboard shortcuts", message)
        super().accept()
