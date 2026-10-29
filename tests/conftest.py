"""Shared fixtures: every test runs headless (offscreen Qt) with the example signal loaded."""

import gc
import os
import pathlib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from pyqtgraph.Qt import QtCore, QtWidgets  # noqa: E402

EXAMPLES = pathlib.Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture(scope="session")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(["spiny-tests"])


@pytest.fixture(autouse=True)
def collect_qt_garbage(qapp):
    """Destroy the widgets of a test right after it, not during an arbitrary later garbage collection

    (a Qt object destroyed by the cyclic garbage collector in the middle of another test can crash the process)
    """
    yield
    gc.collect()
    QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


@pytest.fixture
def player(qapp):
    """The global player, with a fresh copy of the example signal"""
    from spiny.core import player

    player.stop()
    player.loadNewWav(str(EXAMPLES / "arctic_a0002.wav"))
    return player


@pytest.fixture
def example_annotations():
    from spiny.annotations.io.htk_lab import HTKLabelSerialiser

    return HTKLabelSerialiser().load(EXAMPLES / "arctic_a0002.lab")


@pytest.fixture
def no_dialogs(monkeypatch):
    """Replace the message boxes by recorders (they would block a headless run)"""
    calls = []
    for name in ("warning", "critical", "information"):
        monkeypatch.setattr(QtWidgets.QMessageBox, name, lambda *a, _n=name, **k: calls.append((_n, a)))
    return calls
