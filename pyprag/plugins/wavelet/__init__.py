from pyprag.core import plugin_entry_dict
from .extractor import WaveletExtractor
from .control import WaveletController
from .visualisation import WaveletPlotWidget


sp_extractor = WaveletExtractor()
sp_widget = WaveletPlotWidget(sp_extractor)
controller = WaveletController(sp_extractor, sp_widget)

assert controller._name not in plugin_entry_dict
plugin_entry_dict[controller._name] = controller

__all__ = ["WaveletExtractor", "WaveletPlotWidget", "WaveletController", "controller"]
