# NOTE: requires the optional dependency praat-parselmouth. It is only imported when the spectrogram is
#       extracted (it is big), so here we only check that it is installed; the plugin discovery reports the error.
import importlib.util

from spiny.core import DataController, register_plugin

if importlib.util.find_spec("parselmouth") is None:
    raise ModuleNotFoundError("the optional dependency praat-parselmouth is not installed")

from .extractor import SpectrumPraatExtractor
from .visualisation import SpectrogramPraatPlotWidget

sp_extractor = SpectrumPraatExtractor()
sp_widget = SpectrogramPraatPlotWidget(sp_extractor)
controller = DataController("Spectrogram (Praat)", sp_extractor, sp_widget)  # no configuration needed
register_plugin(controller)

__all__ = ["SpectrumPraatExtractor", "SpectrogramPraatPlotWidget", "controller"]
