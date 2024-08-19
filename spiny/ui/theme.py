import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui


def define_dark_palette(app):
    palette = QtGui.QPalette()

    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)

    return palette


def define_light_palette(app):
    pg.setConfigOption("background", "w")
    pg.setConfigOption("foreground", "k")

    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.black)

    return palette


def define_palette(app, dark_activated=False):
    app.setStyle("Fusion")

    if dark_activated:
        palette = define_dark_palette(app)
    else:
        palette = define_light_palette(app)

    app.setPalette(palette)
    app.setStyleSheet(
        """
        QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }
        # QLabel{font-size: 18pt;}
        # QLineEdit{font-size: 18pt;}
        # QButton{font-size: 18pt;}
        # QPushButton{font-size: 18pt;}
        # QGroupBox{font-size: 18pt;}
        # QComboBox{font-size: 18pt;}
        # QTabWidget{font-size: 18pt;}
        # QToolButton{font-size: 18pt;}
        """
    )
