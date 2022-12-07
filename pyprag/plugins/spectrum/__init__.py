from pyprag.core import plugin_entry_list
from .extractor import SpectrumExtractor
from .control import SpectrumController
from .visualisation import SpectrogramPlotWidget


sp_extractor = SpectrumExtractor()
sp_widget = SpectrogramPlotWidget(sp_extractor)
controller = SpectrumController(sp_extractor, sp_widget)

plugin_entry_list.append(controller)

__all__ = ["SpectrumExtractor", "SpectrogramPlotWidget", "SpectrumController", "controller"]
