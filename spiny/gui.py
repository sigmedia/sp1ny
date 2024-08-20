import sys

# Logging
import logging

# Plotting
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


# spiny internal packages
from spiny.ui.theme import define_palette
from spiny.audio import controller as audio_controller
from spiny.audio import player
from spiny.audio import PlayerControllerWidget
from spiny.annotations import controller as annotation_controller
from spiny.visualisation import VisualisationArea, VisualisationController

#####################################################################################################
# Classes
#####################################################################################################


class GUIVisu(QtWidgets.QMainWindow):
    def __init__(self, frameshift):
        super().__init__()

        ##########################################
        # Setup the Menubar
        ##########################################
        menuBar = self.menuBar()
        file_menu = QtWidgets.QMenu("&File", self)

        # Add open shortcut
        self.openAction = QtGui.QAction("&Open wav...", self)
        self.openAction.triggered.connect(self.openFile)
        self.openAction.setShortcut("Ctrl+o")
        file_menu.addAction(self.openAction)

        # Add exit shortcut!
        self.exitAction = QtGui.QAction(("E&xit"), self)
        self.exitAction.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        self.addAction(self.exitAction)
        self.exitAction.triggered.connect(self.close)
        file_menu.addAction(self.exitAction)
        menuBar.addMenu(file_menu)

        ##########################################
        # Setup the toolbar
        ##########################################
        player_toolbar = self.addToolBar("Player")
        player_widget = PlayerControllerWidget()
        player_toolbar.addWidget(player_widget)

        ##########################################
        # Setup the status bar
        ##########################################
        self.statusbar = self.statusBar()
        self._filename_label = QtWidgets.QLabel(player._filename)
        self.statusbar.addPermanentWidget(self._filename_label)

        ##########################################
        # Define the left part of the window
        ##########################################
        self.visualisation_area = VisualisationArea(frameshift)
        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self.visualisation_area)

        ##########################################
        # Define the right part of the window
        ##########################################
        right_layout = QtWidgets.QVBoxLayout()

        # Initialize tab screen
        tabs = QtWidgets.QTabWidget()
        tab1 = VisualisationController(self, self.visualisation_area)
        tabs.addTab(tab1, "Data/Visualization")

        # self._annotation_layout.setParent(self)
        tab2 = QtWidgets.QWidget()
        tabs.addTab(tab2, "Annotations")
        self._annotation_layout = annotation_controller
        self._annotation_layout.setView(self.visualisation_area._dock_annotation)
        self._annotation_layout.resetView()
        tab2.setLayout(self._annotation_layout)

        tab3 = QtWidgets.QWidget()
        tabs.addTab(tab3, "Audio")
        self._audio_layout = audio_controller
        tab3.setLayout(self._audio_layout)

        right_layout.addWidget(tabs)

        ##########################################
        # Finalize the main part layout
        ##########################################
        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(left_layout, 9)
        main_layout.addLayout(right_layout, 3)

        ##########################################
        # Set the window layout
        ##########################################
        cent_widget = QtWidgets.QWidget()
        cent_widget.setLayout(main_layout)
        self.setCentralWidget(cent_widget)

    def openFile(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        # NOTE: how to concatente filters: "All Files (*);;Wav Files (*.wav)"
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Loading wav file", "", "Wav Files (*.wav)", options=options
        )
        if filename:
            self._filename_label.setText(filename)


def build_gui(app, frameshift):
    # Generate application
    define_palette(app)
    win = GUIVisu(frameshift)
    win.setWindowTitle("SpINY")

    # Start the application
    win.show()
    if (sys.flags.interactive != 1) or not hasattr(QtCore, "PYQT_VERSION"):
        app.exec()
