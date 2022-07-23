#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AUTHOR
    - Antti Suni <antti.suni@helsinki.fi>
    - Sébastien Le Maguer <lemagues@tcd.ie>

DESCRIPTION
    Setup script file

LICENSE
    See https://github.com/asuni/wavelet_prosody_toolkit/blob/master/LICENSE.txt
"""

# Needed imports
from setuptools import setup, find_packages


# Define meta-informations variable
REQUIREMENTS = [
    # Math
    "matplotlib",
    "numpy",
    "scipy",
    # Audio/speech
    "librosa",
    "tgt",
    "pyworld",
    "pyaudio",
    # Rendering
    "pyqtgraph>=0.12.1",
]

EXTRA_REQUIREMENTS = {
    # 'reaper': ["pyreaper"],
    # 'docs': [
    #     'sphinx >= 1.4',
    #     'sphinx_rtd_theme',
    #     "numpydoc"
    # ]
}

NAME = "PyPraG"
VERSION = "0.0.1"
AUTHOR = "Sébastien Le Maguer"
DESCRIPTION = ""
# with open("README.rst", "r") as fh:
#     LONG_DESCRIPTION = fh.read()

# The actual setup
setup(
    # Project info.
    name=NAME,
    version=VERSION,
    url="https://github.com/asuni/wavelet_prosody_toolkit",
    # Author info.
    author=AUTHOR,
    author_email="antti.suni@helsinki.fi",
    # Description part
    description=DESCRIPTION,
    # long_description=LONG_DESCRIPTION,
    # long_description_content_type="text/x-rst",
    # Install requirements
    install_requires=REQUIREMENTS,
    extras_require=EXTRA_REQUIREMENTS,
    # Packaging
    packages=find_packages(),  # FIXME: see later to exclude the test (which will be including later)
    # package_data={'': ['configs/default.yaml', 'configs/synthesis.yaml']},
    include_package_data=True,
    # Meta information to sort the project
    classifiers=[
        "Development Status :: 4 - Beta",
        # Audience
        "Intended Audience :: Science/Research",
        # Topics
        "Topic :: Multimedia :: Sound/Audio :: Speech",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Visualization",
        # Pick your license as you wish
        "License :: OSI Approved :: MIT License",
        # Python version (FIXME: fix the list of python version based on travis results)
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    # "Executable" to link
    entry_points={"console_scripts": [], "gui_scripts": ["pyprag = pyprag.pyprag:main"]},
)
