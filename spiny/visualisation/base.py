__all__ = ["DataController"]


class DataController:
    def __init__(self, name, extractor, widget, wav_plot=None):
        self._name = name
        self._extractor = extractor
        self._widget = widget

    def extract(self):
        assert self._extractor is not None
        self._extractor.extract()
        self.refresh()

    def refresh(self):
        assert self._widget is not None
        self._widget.refresh()
