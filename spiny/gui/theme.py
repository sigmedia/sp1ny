import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets


def define_dark_palette() -> QtGui.QPalette:
    """Build the dark palette

    Returns
    -------
    QtGui.QPalette
        The palette
    """
    palette = QtGui.QPalette()

    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)

    return palette


def define_light_palette() -> QtGui.QPalette:
    """Build the light palette (and set the matching pyqtgraph background and foreground)

    Returns
    -------
    QtGui.QPalette
        The palette
    """
    pg.setConfigOption("background", "w")
    pg.setConfigOption("foreground", "k")

    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.black)

    return palette


def define_palette(app: QtWidgets.QApplication, dark_activated: bool = False) -> None:
    """Apply the Fusion style, the light or dark palette and the tooltip style to the application

    Parameters
    ----------
    app : QtWidgets.QApplication
        The application
    dark_activated : bool, optional
        Use the dark palette. (default: False)
    """
    app.setStyle("Fusion")

    if dark_activated:
        palette = define_dark_palette()
    else:
        palette = define_light_palette()

    app.setPalette(palette)
    app.setStyleSheet("""
        QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }
        /* Uncomment to enlarge the fonts (e.g. for demos)
        QLabel{font-size: 18pt;}
        QLineEdit{font-size: 18pt;}
        QPushButton{font-size: 18pt;}
        QGroupBox{font-size: 18pt;}
        QComboBox{font-size: 18pt;}
        QTabWidget{font-size: 18pt;}
        QToolButton{font-size: 18pt;}
        */
        """)
