# NOTE: requires the optional dependency praat-parselmouth; import errors are reported by the plugin discovery
from spiny.core import register_plugin
from .extractor import SpectrumPraatExtractor
from .control import SpectrumPraatController
from .visualisation import SpectrogramPraatPlotWidget

sp_extractor = SpectrumPraatExtractor()
sp_widget = SpectrogramPraatPlotWidget(sp_extractor)
controller = SpectrumPraatController(sp_extractor, sp_widget)
register_plugin(controller)

__all__ = ["SpectrumPraatExtractor", "SpectrogramPraatPlotWidget", "SpectrumPraatController", "controller"]
