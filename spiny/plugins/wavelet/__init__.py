# NOTE: requires the optional dependency wavelet_prosody_toolkit; import errors are reported by the plugin discovery
from spiny.core import register_plugin
from .extractor import WaveletExtractor
from .control import WaveletController
from .visualisation import WaveletPlotWidget

sp_extractor = WaveletExtractor()
sp_widget = WaveletPlotWidget(sp_extractor)
controller = WaveletController(sp_extractor, sp_widget)
register_plugin(controller)

__all__ = ["WaveletExtractor", "WaveletPlotWidget", "WaveletController", "controller"]
