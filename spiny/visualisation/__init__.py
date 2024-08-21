from .core import VisualisationController
from .core import DataDock

__all__ = ["DataDock", "VisualisationController"]

import importlib
import pkgutil

import spiny.plugin.visualisation  # NOTE: we import the full plugins package path to dynamically parse the list of plugins

# Discover plugins
def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


discovered_plugins = {name: importlib.import_module(name) for _, name, _ in iter_namespace(spiny.plugin.visualisation)}
