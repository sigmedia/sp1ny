import sys

import pytest

from conftest import EXAMPLES


@pytest.mark.parametrize(
    "argv, message",
    [
        (["-w", "missing.wav"], "--wav-file"),
        (["--wav_file", "missing.wav"], "--wav-file"),
        (["-w", str(EXAMPLES / "arctic_a0002.wav"), "-a", "missing.lab"], "--annotation-file"),
        (["-w", str(EXAMPLES / "arctic_as.wav"), "-c", str(EXAMPLES / "arctic_as.neur")], "--dimension"),
    ],
)
def test_invalid_arguments(monkeypatch, capsys, argv, message):
    from spiny.main import main

    monkeypatch.setattr(sys, "argv", ["spiny"] + argv)
    with pytest.raises(SystemExit):
        main()
    assert message in capsys.readouterr().err


def test_importing_spiny_creates_no_widget():
    import subprocess

    code = "import spiny.main, spiny.ui, spiny.annotations; from pyqtgraph.Qt import QtWidgets; "
    code += "assert QtWidgets.QApplication.instance() is None"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_without_audio_file_a_dialog_asks_for_it(monkeypatch, qapp):
    import spiny.main as spiny_main

    asked = []
    monkeypatch.setattr(sys, "argv", ["spiny"])
    monkeypatch.setattr(spiny_main, "ask_audio_file", lambda: asked.append(True) or "")
    spiny_main.main()  # cancelled dialog: returns without building the GUI
    assert asked == [True]


def test_packaged_application_starts(tmp_path):
    """The application starts and quits on its own when SPINY_AUTOQUIT_MS is set (used to check the binaries)"""
    import os
    import subprocess

    env = dict(os.environ, SPINY_AUTOQUIT_MS="500", QT_QPA_PLATFORM="offscreen")
    code = "from spiny.main import main; main()"
    result = subprocess.run([sys.executable, "-c", code, "-w", str(EXAMPLES / "arctic_a0002.wav")], env=env, timeout=60)
    assert result.returncode == 0
