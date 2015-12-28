from datetime import datetime
import functools
import json
import sys
import warnings

from dateutil.tz import tzlocal
import numpy as np
import pytz
from PyQt4 import QtGui, uic
from PyQt4.QtCore import QThread, SIGNAL
from PyQt4.QtGui import QListWidgetItem, QFont
import requests
from vispy import gloo, app
import websocket

main_app = QtGui.QApplication(sys.argv)

with warnings.catch_warnings(record=True):
    WindowTemplate, TemplateBaseClass = uic.loadUiType('qt-designer.ui')

    class MainWindow(TemplateBaseClass):
        def __init__(self):
            TemplateBaseClass.__init__(self)
            self.ui = WindowTemplate()
            self.ui.setupUi(self)
            self.matches = []
            print(self.matches)
            self.ui.start_button.clicked.connect(functools.partial(self.start_websocket))
            start_matches = requests.get('https://api.exchange.coinbase.com/products/BTC-USD/trades').json()
            for message in reversed(start_matches):
                self.add_match(message)
            # self.ui.canvas = MainCanvas(self.ui.canvas, self)

        def start_websocket(self):
            thread = ListenWebsocket()
            self.connect(thread, thread.match_signal, self.add_match)
            self.connect(thread, thread.sequence_signal, self.update_sequence)
            thread.start()

        def add_match(self, message):
            self.matches += [message]
            size = '{0:.8f}'.format(float(message['size']))
            timestamp = datetime.strptime(message['time'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)
            while len(size) < 12:
                size = ' ' + size
            item = QListWidgetItem('{0} {1:.2f} {2}'.format(size, float(message['price']), timestamp.astimezone(tzlocal()).strftime('%H:%M:%S.%f')))
            item.setFont(QFont('Courier New'))
            self.ui.matches_list.insertItem(-1, item)

        def update_sequence(self, sequence):
            self.ui.sequence_label.setText('Sequence: {0}'.format(sequence))


# @asyncio.coroutine
# def master(main_window):
#     main_window.websocket = True
#     coinbase_websocket = yield from websockets.connect("wss://ws-feed.exchange.coinbase.com")
#     yield from coinbase_websocket.send('{"type": "subscribe", "product_id": "BTC-USD"}')
#     while main_window.websocket:
#         message = yield from coinbase_websocket.recv()
#         message = json.loads(message)
#         main_window.ui.sequence_label.setText('Sequence: {0}'.format(message['sequence']))
#         if message['type'] == 'match':
#             main_window.ui.canvas.match_prices += [float(message['price'])]
#             main_window.ui.canvas.match_dates += [datetime.strptime(message['time'], '%Y-%m-%dT%H:%M:%S.%fZ')]

class ListenWebsocket(QThread):
    def __init__(self):
        super(ListenWebsocket, self).__init__(main_app)
        self.sequence_signal = SIGNAL("sequence_signal")
        self.match_signal = SIGNAL("match_signal")
        self.WS = websocket.WebSocketApp("wss://ws-feed.exchange.coinbase.com",
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)

    def run(self):
        self.WS.on_open = self.on_open
        self.WS.run_forever()

    def on_open(self, ws):
        self.WS.send('{"type": "subscribe", "product_id": "BTC-USD"}')

    def on_message(self, ws, message):
        message = json.loads(message)
        self.emit(self.sequence_signal, message['sequence'])
        if message['type'] == 'match':
            self.emit(self.match_signal, message)

    def on_error(self, ws, error):
        print(error)

    def on_close(self, ws):
        return True


class MainCanvas(app.Canvas):
    def __init__(self, parent, main_window):
        app.Canvas.__init__(self, keys='interactive', parent=parent)
        self.match_dates = []
        self.match_prices = []
        for match in main_window.matches:
            self.match_dates += [datetime.strptime(match['time'], '%Y-%m-%dT%H:%M:%S.%fZ')]
            self.match_prices += [float(match['price'])]
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

        # print(np.c_[np.array(])].astype(np.float32))
        self._timer = app.Timer('auto', connect=self.on_timer_event, start=True)

    # def calculate_plot(self):

    def on_timer_event(self, event):
        self.program['a_position'] = np.c_[
            np.linspace(-1.0, +1.0, 1000),
            np.random.uniform(-0.5, +0.5, 1000)].astype(np.float32)
        self.update()
        self.show()

    def on_resize(self, event):
        gloo.set_viewport(0, 0, *event.size)

    def on_draw(self, event):
        gloo.clear((1, 1, 1, 1))
        self.program.draw('line_strip')


def main():
    main_window = MainWindow()
    main_window.show()
    main_window.raise_()
    sys.exit(main_app.exec_())


if __name__ == '__main__':
    main()
