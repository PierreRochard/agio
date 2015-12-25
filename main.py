import asyncio
import functools
import sys
import time
import warnings

import numpy as np
from PyQt4 import QtGui, uic
from quamash import QEventLoop, QThreadExecutor
from vispy import gloo, app


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
            self.ui.canvas = MainCanvas(self.ui.canvas)


class MainCanvas(app.Canvas):
    def __init__(self, parent):
        app.Canvas.__init__(self, keys='interactive', parent=parent)
        vertex = """
        attribute vec2 a_position;
        void main (void)
        {
            gl_Position = vec4(a_position, 0.0, 1.0);
        }
        """

        fragment = """
        void main()
        {
            gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        }
        """
        self.program = gloo.Program(vertex, fragment)
        self.program['a_position'] = np.c_[
            np.linspace(-1.0, +1.0, 1000),
            np.random.uniform(-0.5, +0.5, 1000)].astype(np.float32)
        self.show()

    def on_resize(self, event):
        gloo.set_viewport(0, 0, *event.size)

    def on_draw(self, event):
        gloo.clear((1, 1, 1, 1))
        self.program.draw('line_strip')


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
