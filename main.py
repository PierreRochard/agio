import asyncio
import functools
import sys
import time
import warnings

import numpy as np
from PyQt4 import QtGui, uic
from quamash import QEventLoop, QThreadExecutor
from vispy import plot as vp
from vispy.app.qt import QtSceneCanvas
from vispy.scene import visuals
from vispy.scene.subscene import SubScene
from vispy.util import load_data_file
from vispy import gloo, keys, app


@asyncio.coroutine
def master(progress):
    yield from first_50(progress)
    loop = asyncio.get_event_loop()
    with QThreadExecutor(1) as executor:
        yield from loop.run_in_executor(executor, functools.partial(last_50, progress, loop))


@asyncio.coroutine
def first_50(progress):
    for i in range(50):
        progress.setValue(i)
        yield from asyncio.sleep(.01)


def last_50(progress, loop):
    for i in range(50, 100):
        loop.call_soon_threadsafe(progress.setValue, i)
        time.sleep(.01)

with warnings.catch_warnings(record=True):
    WindowTemplate, TemplateBaseClass = uic.loadUiType('qt-designer.ui')

    class MainWindow(TemplateBaseClass):
        def __init__(self):
            TemplateBaseClass.__init__(self)

            self.ui = WindowTemplate()
            self.ui.setupUi(self)
            self.ui.progressBar.setRange(0, 99)
            self.ui.canvas = MainCanvas(self.ui.frame)
            # @self.ui.canvas.connect
            # def on_resize(event):
            #     gloo.set_viewport(0, 0, *event.size)


class MainCanvas(QtSceneCanvas):
    def __init__(self, parent):
        super(QtSceneCanvas, self).__init__(parent)
        self.scene = SubScene()
        data = np.linspace(0, 100)
        visuals.LinePlot(data=data, parent=self.scene)
    def on_resize(self, event):
        self.apply_zoom()


def main():
    app = QtGui.QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    main_window = MainWindow()
    main_window.show()
    main_window.raise_()
    with loop:
        try:
            loop.run_until_complete(master(main_window.ui.progressBar))
        except RuntimeError:
            sys.exit(0)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
