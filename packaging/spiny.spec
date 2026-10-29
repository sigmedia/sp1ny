# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification of the standalone Sp1NY application

Build (from this directory, in an environment where spiny is installed with ``pip install .`` and
praat-parselmouth is installed for the Praat plugin)::

    pyinstaller --noconfirm spiny.spec

The result is a folder (dist/spiny) rather than a single file: a single-file executable unpacks
itself in a temporary directory at every launch, which makes it start several seconds slower.
On macOS, the folder is wrapped in an application bundle (dist/Sp1NY.app).

Notes
-----
- The PortAudio (playback) and libsndfile (audio files) libraries are shipped inside the sounddevice
  and soundfile wheels on Windows and macOS, and bundled from there. On Linux, sounddevice uses the
  system PortAudio: the libportaudio2 package must be installed on the machine running the binary.
- The wavelet plugin is not bundled (its dependency is not packaged properly upstream); the plugin
  discovery skips it.
"""

import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# The plugins are discovered at runtime (pkgutil), so PyInstaller cannot find them by itself
hiddenimports = collect_submodules("spiny.plugins") + collect_submodules("spiny.raw_data")

# pyqtgraph's colormap tables and ipapy's IPA tables are data files
datas = collect_data_files("pyqtgraph", includes=["colors/maps/*"]) + collect_data_files("ipapy")

# Large packages which may be installed in the build environment but are not used by spiny
excludes = [
    "IPython",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "librosa",
    "matplotlib",
    "numba",
    "pandas",
    "scipy",
    "tkinter",
    "wavelet_prosody_toolkit",
    "yaml",
]

# Qt modules pulled by Qt plugins (virtual keyboard, PDF image format, ...) but not used by spiny, matched on the
# library names of every platform (libQt6Qml.so, Qt6Qml.dll, QtQml.framework, ...)
UNUSED_QT = ("Qt6Qml", "QtQml", "Qt6Quick", "QtQuick", "VirtualKeyboard", "virtualkeyboard", "Qt6Pdf", "QtPdf", "qpdf")


def is_used(entry):
    """Tell if a (destination, source, type) entry of the analysis must be bundled

    Parameters
    ----------
    entry : tuple(str, str, str)
        The entry

    Returns
    -------
    bool
        False for the unused Qt modules and for Qt's own translations (spiny is in English)
    """
    destination = entry[0].replace("\\", "/")
    return not (any(name in destination for name in UNUSED_QT) or "Qt/translations/" in destination)

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
a.binaries = [entry for entry in a.binaries if is_used(entry)]
a.datas = [entry for entry in a.datas if is_used(entry)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="spiny",
    debug=False,
    strip=False,
    upx=False,
    # A console is only useful on Linux (started from a terminal); on Windows and macOS it is a GUI application
    console=sys.platform.startswith("linux"),
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="spiny")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Sp1NY.app",
        bundle_identifier="org.sigmedia.sp1ny",
        info_plist={"NSHighResolutionCapable": True},
    )
