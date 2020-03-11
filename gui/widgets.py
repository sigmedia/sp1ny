import numpy as np
import pyqtgraph as pg

from .items import *


class SelectableWavPlotWidget(pg.PlotWidget):

    def __init__(self, wav, max_dur, parent=None, background='default', **kwargs):
        pg.GraphicsView.__init__(self, parent, background)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.enableMouse(False)

        self.plotItem = SelectablePlotItem(**kwargs)
        self.setCentralItem(self.plotItem)

        self._wav = wav

        # Compute maximum point
        max_point = int(max_dur * self._wav[1])
        if max_point > self._wav[0].shape[0]:
            max_point = self._wav[0].shape[0]

        # Plot principal
        self._main_plot = self.plotItem.plot(x=np.linspace(0, max_dur, max_point),
                                             y=self._wav[0][:max_point])

        if max_point < self._wav[0].shape[0]:
            self.plotItem.plot(x=np.linspace(max_dur, self._wav[0].shape[0]/float(self._wav[1]),
                                             self._wav[0].shape[0]-max_point),
                               y=self._wav[0][max_point:], pen={'color': "F00"})

        ## Explicitly wrap methods from plotItem
        ## NOTE: If you change this list, update the documentation above as well.
        for m in ['addItem', 'removeItem', 'autoRange', 'clear', 'setXRange',
                  'setYRange', 'setRange', 'setAspectLocked', 'setMouseEnabled',
                  'setXLink', 'setYLink', 'enableAutoRange', 'disableAutoRange',
                  'setLimits', 'register', 'unregister', 'viewRect']:
            setattr(self, m, getattr(self.plotItem, m))
        #QtCore.QObject.connect(self.plotItem, QtCore.SIGNAL('viewChanged'), self.viewChanged)
        self.plotItem.sigRangeChanged.connect(self.viewRangeChanged)



class SelectableImagePlotWidget(pg.PlotWidget):

    def __init__(self, data, frameshift, ticks, parent=None, background='default', **kwargs):

        pg.GraphicsView.__init__(self, parent, background)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        self.enableMouse(False)


        self._data = data
        self._y_scale = 16e03 # FIXME: solve this!

        # Generate image data
        img = pg.ImageItem()
        img.setImage(self._data.T)
        img.scale(frameshift, 1.0/(self._data.shape[1]/self._y_scale))

        # Define and assign histogram
        hist = pg.HistogramLUTWidget()
        hist.setImageItem(img)
        hist.gradient.restoreState(
            {'mode': 'rgb', 'ticks': ticks}
        )

        # Generate plot
        self.plotItem = SelectablePlotItem(**kwargs)
        self.plotItem.getViewBox().addItem(img)
        self.setCentralItem(self.plotItem)


        ## Explicitly wrap methods from plotItem
        ## NOTE: If you change this list, update the documentation above as well.
        for m in ['addItem', 'removeItem', 'autoRange', 'clear', 'setXRange',
                  'setYRange', 'setRange', 'setAspectLocked', 'setMouseEnabled',
                  'setXLink', 'setYLink', 'enableAutoRange', 'disableAutoRange',
                  'setLimits', 'register', 'unregister', 'viewRect']:
            setattr(self, m, getattr(self.plotItem, m))
        #QtCore.QObject.connect(self.plotItem, QtCore.SIGNAL('viewChanged'), self.viewChanged)
        self.plotItem.sigRangeChanged.connect(self.viewRangeChanged)
