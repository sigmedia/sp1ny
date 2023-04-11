try:
    from pyprag.core import plugin_entry_dict
    from .extractor import SpectrumPraatExtractor
    from .control import SpectrumPraatController
    from .visualisation import SpectrogramPraatPlotWidget

    sp_extractor = SpectrumPraatExtractor()
    sp_widget = SpectrogramPraatPlotWidget(sp_extractor)
    controller = SpectrumPraatController(sp_extractor, sp_widget)

    assert controller._name not in plugin_entry_dict
    plugin_entry_dict[controller._name] = controller

    __all__ = ["SpectrumPraatExtractor", "SpectrogramPraatPlotWidget", "SpectrumPraatController", "controller"]

except ModuleNotFoundError as ex:
    import logging

    logger = logging.getLogger()
    logger.warn("Couldn't load the module, activate debug mode to see the reason")
    logger.debug(str(ex))
