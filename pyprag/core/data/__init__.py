from pyprag.core import plugin_entry_list
from .extractor import RawDataExtractor
from .visualisation import RawDataPlotWidget
from .control import RawDataController

extractor = RawDataExtractor()
widget = RawDataPlotWidget(extractor)
controller = RawDataController(extractor, widget)

plugin_entry_list.append(controller)

__all__ = ["RawDataExtractor", "RawDataPlotWidget", "RawDataController", "controller"]
