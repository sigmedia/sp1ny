from spiny.core import register_plugin
from .extractor import RawDataExtractor
from .visualisation import RawDataPlotWidget
from .control import RawDataController

extractor = RawDataExtractor()
widget = RawDataPlotWidget(extractor)
controller = RawDataController(extractor, widget)

register_plugin(controller)

__all__ = ["RawDataExtractor", "RawDataPlotWidget", "RawDataController", "controller"]
