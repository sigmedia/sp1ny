from spiny.core import register_plugin
from .extractor import SpectrumExtractor
from .control import SpectrumController
from .visualisation import SpectrogramPlotWidget

sp_extractor = SpectrumExtractor()
sp_widget = SpectrogramPlotWidget(sp_extractor)
controller = SpectrumController(sp_extractor, sp_widget)
register_plugin(controller)

__all__ = ["SpectrumExtractor", "SpectrogramPlotWidget", "SpectrumController", "controller"]
