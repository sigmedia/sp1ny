import gc
import sys

import pytest
from pyqtgraph.Qt import QtCore, QtWidgets

from conftest import EXAMPLES


def test_extended_combobox_completer(qapp):
    from spiny.gui.helpers.widgets import ExtendedComboBox

    box = ExtendedComboBox()
    box.addItems(["a", "b"])
    emitted = []
    box.textActivated.connect(emitted.append)
    box.on_completer_activated("b")
    assert box.currentText() == "b" and emitted == ["b"]


def test_colormaps_are_available_without_matplotlib(qapp):
    from spiny.gui.colormaps import COLORMAP_NAMES, colormap_ticks

    for name in COLORMAP_NAMES:
        ticks = colormap_ticks(name)
        assert len(ticks) == 10 and ticks[0][0] == 0.0 and ticks[-1][0] == 1.0
        assert all(len(color) == 4 and all(0 <= c <= 255 for c in color) for _, color in ticks)


def test_colormaps_match_matplotlib(qapp):
    mpl = pytest.importorskip("matplotlib")
    import numpy as np

    from spiny.gui.colormaps import COLORMAP_NAMES, get_colormap

    positions = np.linspace(0, 1, 33)
    for name in COLORMAP_NAMES:
        expected = mpl.colormaps[name](positions)[:, :3] * 255
        obtained = get_colormap(name).map(positions, mode="float")[:, :3] * 255
        # pyqtgraph stores its maps on 8 bits, and ships the original cividis (matplotlib uses a revised table)
        tolerance = 25 if name == "cividis" else 5
        assert np.abs(obtained - expected).max() < tolerance, name


def test_unknown_colormap(qapp):
    from spiny.gui.colormaps import get_colormap

    with pytest.raises(ValueError):
        get_colormap("jet")


@pytest.fixture(scope="module")
def window(qapp):
    # NOTE: one window for the module: the window takes ownership of the (singleton) control layouts
    from spiny.core import player
    from spiny.raw_data import controller as raw_controller
    from spiny.ui import GUIVisu, discover_plugins, install_exception_hook

    player.loadNewWav(str(EXAMPLES / "arctic_as.wav"))
    raw_controller.loadCoefficientFile(str(EXAMPLES / "arctic_as.neur"), -50, 6.4)
    discover_plugins()
    previous_hook = sys.excepthook
    win = GUIVisu()
    install_exception_hook(win)
    win.show()

    # Modal dialogs would block a headless run: record them instead, the tests check there is none
    dialogs = []
    with pytest.MonkeyPatch.context() as patch:
        for name in ("warning", "critical", "information"):
            patch.setattr(QtWidgets.QMessageBox, name, lambda *a, **k: dialogs.append(a))
        win.dialogs = dialogs
        yield win
    sys.excepthook = previous_hook

    # Destroy the window now (not at an arbitrary later garbage collection) so that the next tests
    # get fresh controllers instead of controllers whose widgets disappear under their feet
    win.close()
    win.deleteLater()
    del win
    gc.collect()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_every_plugin_renders_with_time_on_x(window):
    plugins = [window._plugin_list.itemText(i) for i in range(window._plugin_list.count())]
    assert {"Raw DATA", "Spectrogram"} <= set(plugins)
    for name in plugins + plugins:  # selecting a plugin twice must work too
        window._plugin_list.setCurrentText(name)
        QtWidgets.QApplication.processEvents()
        widget = window._visualisation_area._dock_coef._data_plot
        image = widget._imageItem
        x_max = widget._plotItem.getViewBox().state["limits"]["xLimits"][1]
        assert image.mapRectToParent(image.boundingRect()).width() == pytest.approx(x_max, rel=0.05), name
    window._cmap_list.setCurrentText("magma")
    assert window.dialogs == []


def test_data_widget_renders_only_the_visible_slice(qapp):
    import numpy as np
    from pyqtgraph.Qt import QtGui

    from spiny.gui.widgets import DataWidget

    widget = DataWidget()
    widget.resize(800, 300)
    widget.show()
    data = np.arange(100_000 * 20, dtype=np.float32).reshape(100_000, 20)
    widget.setLimits(xMin=0, xMax=1000)
    widget.setImageData(data, transform=QtGui.QTransform.fromScale(0.01, 1.0))  # 10 ms frames
    widget.setXRange(500, 510, padding=0)  # 10 s visible = 1000 frames
    QtWidgets.QApplication.processEvents()
    widget.grab()

    image = widget._imageItem
    assert image.image.base is not None  # a view on the data, not a copy
    assert image.image.shape[0] <= 2000 + 2
    rect = image.mapRectToParent(image.boundingRect())
    assert rect.left() <= 500 and rect.right() >= 510  # the slice covers the visible range, at the right place
    assert image.qimage.width() <= image.image.shape[0]

    widget.setXRange(0, 1000, padding=0)  # zoom out: the slice grows to the whole data
    QtWidgets.QApplication.processEvents()
    widget.grab()
    assert image.image.shape[0] == data.shape[0] and image.qimage.width() < 2000
    widget.close()


def test_switching_plugin_releases_the_previous_data(window):
    from spiny.core import plugin_entry_dict

    window._plugin_list.setCurrentText("Spectrogram")
    QtWidgets.QApplication.processEvents()
    spectrum = plugin_entry_dict["Spectrogram"]
    assert spectrum.widget._imageItem.image is not None and spectrum._extractor._spectrum.size > 100

    window._plugin_list.setCurrentText("Raw DATA")
    QtWidgets.QApplication.processEvents()
    assert spectrum.widget._imageItem.image is None and spectrum._extractor._spectrum.size == 100
    assert plugin_entry_dict["Raw DATA"].widget._imageItem.image is not None


def test_open_wav_refreshes_the_views(window):
    from spiny.core import player

    window.loadWav(str(EXAMPLES / "arctic_a0002.wav"))
    x_max = window._visualisation_area._dock_wav.wav_plot.plotItem.vb.state["limits"]["xLimits"][1]
    assert x_max == pytest.approx(player.duration) == pytest.approx(3.755)
    assert window._filename_label.text().endswith("arctic_a0002.wav")


def test_unhandled_exceptions_are_shown(window):
    window.dialogs.clear()
    sys.excepthook(ValueError, ValueError("boom"), None)
    assert len(window.dialogs) == 1


def test_data_widget_does_not_import_matplotlib(qapp):
    import subprocess

    code = (
        "import sys; from pyqtgraph.Qt import QtWidgets; app = QtWidgets.QApplication([]); "
        "from spiny.gui.widgets import DataWidget; DataWidget(); "
        "assert 'matplotlib' not in sys.modules; import importlib.util; "
        "assert importlib.util.find_spec('matplotlib') is None or __import__('matplotlib')"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_set_matrix_places_the_data_in_seconds_and_y_range(qapp):
    import numpy as np

    from spiny.gui.widgets import DataWidget

    widget = DataWidget()
    widget.resize(600, 300)
    widget.show()
    widget.setMatrix(np.zeros((200, 50), dtype=np.uint8), 0.01, (100.0, 4100.0), levels=(0, 255))
    QtWidgets.QApplication.processEvents()

    limits = widget._plotItem.getViewBox().state["limits"]
    assert limits["xLimits"] == [0, 2.0] and limits["yLimits"] == [100.0, 4100.0]
    image = widget._imageItem
    rect = image.mapRectToParent(image.boundingRect())
    assert rect.left() == pytest.approx(0) and rect.right() == pytest.approx(2.0)
    assert rect.top() == pytest.approx(100.0) and rect.bottom() == pytest.approx(4100.0)
    widget.close()
