from pyprag.core import plugin_entry_dict
from .extractor import SpectrumExtractor
from .control import SpectrumController
from .visualisation import SpectrogramPlotWidget


sp_extractor = SpectrumExtractor()
sp_widget = SpectrogramPlotWidget(sp_extractor)
controller = SpectrumController(sp_extractor, sp_widget)

assert controller._name not in plugin_entry_dict
plugin_entry_dict[controller._name] = controller

__all__ = ["SpectrumExtractor", "SpectrogramPlotWidget", "SpectrumController", "controller"]
