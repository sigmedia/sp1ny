from pyprag.core import plugin_entry_dict
from .extractor import RawDataExtractor
from .visualisation import RawDataPlotWidget
from .control import RawDataController

extractor = RawDataExtractor()
widget = RawDataPlotWidget(extractor)
controller = RawDataController(extractor, widget)

assert controller._name not in plugin_entry_dict
plugin_entry_dict[controller._name] = controller

__all__ = ["RawDataExtractor", "RawDataPlotWidget", "RawDataController", "controller"]
