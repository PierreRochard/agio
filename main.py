import asyncio
import functools
import json
import sys
import time
import warnings

import numpy as np
from PyQt4 import QtGui, uic
from quamash import QEventLoop
from vispy import gloo, app
import websockets


@asyncio.coroutine
def master(main_window):
    main_window.websocket = True
    coinbase_websocket = yield from websockets.connect("wss://ws-feed.exchange.coinbase.com")
    yield from coinbase_websocket.send('{"type": "subscribe", "product_id": "BTC-USD"}')
    while main_window.websocket:
        message = yield from coinbase_websocket.recv()
        message = json.loads(message)
        main_window.ui.sequence_label.setText('Sequence: {0}'.format(message['sequence']))

with warnings.catch_warnings(record=True):
    WindowTemplate, TemplateBaseClass = uic.loadUiType('qt-designer.ui')


    class MainWindow(TemplateBaseClass):
        def __init__(self):
            TemplateBaseClass.__init__(self)
            self.ui = WindowTemplate()
            self.ui.setupUi(self)
            self.ui.canvas = MainCanvas(self.ui.canvas)
            loop = asyncio.get_event_loop()
            self.websocket = False
            self.ui.start_button.clicked.connect(lambda: loop.run_until_complete(master(self)))
            self.ui.stop_button.clicked.connect(functools.partial(self.toggle_websocket, False))

        def toggle_websocket(self, status):
            self.websocket = status


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
    main_app = QtGui.QApplication(sys.argv)
    loop = QEventLoop(main_app)
    asyncio.set_event_loop(loop)
    main_window = MainWindow()
    main_window.show()
    main_window.raise_()
    sys.exit(main_app.exec_())


if __name__ == '__main__':
    main()
