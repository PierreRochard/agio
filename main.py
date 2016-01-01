import base64
import hashlib
import hmac
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
import json
import math
import sys
import time
import warnings
from pprint import pformat

from dateutil.parser import parse
from dateutil.tz import tzlocal
import numpy as np
import pytz
from PyQt4 import QtGui, uic
from PyQt4.QtCore import QThread, SIGNAL, QUrl, Qt, QTimer, QObject
from PyQt4.QtGui import QColor, QTableWidgetItem, QHeaderView, QTreeWidgetItem
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest
from decimal import Decimal
from vispy import gloo, app
import websocket

from config import COINBASE_EXCHANGE_API_KEY, COINBASE_EXCHANGE_API_SECRET, COINBASE_EXCHANGE_API_PASSPHRASE
from order_book.book import Book

main_app = QtGui.QApplication(sys.argv)


class LimitTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, parent=None, columns=[]):
        QtGui.QTreeWidgetItem.__init__(self, parent, columns)

    def __lt__(self, otherItem):
        column = self.treeWidget().sortColumn()
        return float(self.text(column)) < float(otherItem.text(column))


with warnings.catch_warnings(record=True):
    WindowTemplate, TemplateBaseClass = uic.loadUiType('qt-designer.ui')


    class MainWindow(TemplateBaseClass):
        def __init__(self):
            TemplateBaseClass.__init__(self)
            self.order_book = Book()
            self.manager = QNetworkAccessManager(self)
            self.ui = WindowTemplate()
            self.ui.setupUi(self)
            self.matches = []
            self.get_order_book()
            self.start_websocket()
            self.get_recent_matches()
            self.get_fills()

            self.ui.bid_tree.setColumnCount(2)
            self.ui.bid_tree.setHeaderLabels(['Price', 'Size', 'Value', 'Count', 'Order'])
            self.ui.bid_tree.setItemsExpandable(True)
            self.bid_tree = {}
            self.get_open_orders()

            self.ui.refresh_fills.clicked.connect(self.get_fills)
            self.ui.refresh_open_orders.clicked.connect(self.get_open_orders)
            # self.ui.canvas = MainCanvas(self.ui.canvas, self)
            self.timer = QTimer()
            self.connect(self.timer, SIGNAL("timeout()"), self.refresh_order_book)
            self.timer.start(500)

        def refresh_order_book(self):
            prices = sorted(self.order_book.bids.price_map.keys(), reverse=True)[:100]
            self.ui.bid_tree.setSortingEnabled(False)
            self.ui.bid_tree.clear()
            self.bid_tree = {}
            for price in prices:
                for order in self.order_book.bids.price_map[price]:
                    self.add_limit_order(order, 'bid')
            self.ui.bid_tree.setSortingEnabled(True)
            self.ui.bid_tree.sortItems(0, Qt.DescendingOrder)

        def get_order_book(self):
            request = QNetworkRequest()
            url = QUrl('https://api.exchange.coinbase.com/products/BTC-USD/book')
            url.addQueryItem('level', '3')
            request.setUrl(url)
            response = self.manager.get(request)
            response.finished.connect(self.process_order_book)

        def process_order_book(self):
            reply = self.sender()
            raw = reply.readAll()
            response = json.loads(raw.data().decode('utf-8'))

            [self.order_book.bids.insert_order(bid[2], Decimal(bid[1]), Decimal(bid[0]), initial=True) for bid in response['bids']]
            [self.order_book.asks.insert_order(ask[2], Decimal(ask[1]), Decimal(ask[0]), initial=True) for ask in response['asks']]
            self.order_book.level3_sequence = response['sequence']

        def process_message(self, message):
            try:
                self.order_book.process_message(message)
            except KeyError:
                pass

        def add_limit_order(self, limit_order, side):
            if side == 'bid':
                price = '{0:,.2f}'.format(float(limit_order['price']))
                size = str(limit_order['size'])
                value = '{0:,.2f}'.format((round(Decimal(size) * Decimal(price), 2)))
                order_id = limit_order['order_id']
                parent_price = self.bid_tree.get(price)

                if not parent_price:
                    self.bid_tree[price] = {}
                    self.bid_tree[price][order_id] = {'price': price, 'size': size, 'value': value, 'order_id': order_id}
                    self.bid_tree[price]['parent'] = LimitTreeWidgetItem(self.ui.bid_tree, [price, size, value, '', order_id])
                    alpha = min(255, int(20.0 * math.sqrt(float(size))) + 20)
                    for column in range(0, 6):
                        self.bid_tree[price]['parent'].setBackgroundColor(column, QColor(0, 255, 0, alpha))
                else:
                    self.bid_tree[price][order_id] = {'price': price, 'size': size, 'value': value, 'order_id': order_id}
                    self.ui.bid_tree.takeTopLevelItem((self.ui.bid_tree.indexOfTopLevelItem(parent_price['parent'])))
                    del parent_price['parent']
                    orders = [Decimal(self.bid_tree[price][order_id]['size'])
                              for order_id in self.bid_tree[price]
                              if 'size' in self.bid_tree[price][order_id]]
                    cumulative_size = sum(orders)
                    cumulative_value = '{0:,.2f}'.format(round(cumulative_size * Decimal(price), 2))
                    count = len(orders)
                    parent_price['parent'] = LimitTreeWidgetItem(self.ui.bid_tree,
                                                                 [price, str(cumulative_size), cumulative_value, str(count), ''])
                    for order_id in self.bid_tree[price]:
                        if not isinstance(self.bid_tree[price][order_id], LimitTreeWidgetItem):
                            alpha = min(255, int(20.0 * math.sqrt(float(self.bid_tree[price][order_id]['size']))) + 20)
                            new_item = QTreeWidgetItem(parent_price['parent'],
                                                       ['',
                                                        self.bid_tree[price][order_id]['size'],
                                                        self.bid_tree[price][order_id]['value'],
                                                        '',
                                                        self.bid_tree[price][order_id]['order_id']])
                            for column in range(0, 6):
                                new_item.setBackgroundColor(column, QColor(0, 255, 0, alpha))
                    alpha = min(255, int(20.0 * math.sqrt(float(size))) + 20)
                    for column in range(0, 6):
                        self.bid_tree[price]['parent'].setBackgroundColor(column, QColor(0, 255, 0, alpha))

        def get_recent_matches(self):
            request = QNetworkRequest()
            request.setUrl(QUrl('https://api.exchange.coinbase.com/products/BTC-USD/trades'))
            response = self.manager.get(request)
            response.finished.connect(self.process_matches)

        def process_matches(self):
            reply = self.sender()
            raw = reply.readAll()
            response = json.loads(raw.data().decode('utf-8'))
            for message in reversed(response):
                self.add_match(message)

        def add_match(self, message):
            alpha = min(255, int(20.0 * math.sqrt(float(message['size']))) + 20)
            message['value'] = '{0:,.2f}'.format(float(message['price']) * float(message['size']))
            message['price'] = '{0:,.2f}'.format(float(message['price']))
            message['size'] = '{0:,.4f}'.format(float(message['size']))
            try:
                message['time'] = message['time'].astimezone(tzlocal()).strftime('%H:%M:%S')
            except AttributeError:
                message['time'] = parse(message['time']).astimezone(tzlocal()).strftime('%H:%M:%S')
            if message['side'] == 'buy':
                message['color'] = QColor(255, 0, 0, alpha)
            else:
                message['color'] = QColor(0, 255, 0, alpha)
            self.matches += [message]
            headers = ['Price', 'Size', 'Value', 'Time', 'Taker Order ID']
            self.ui.matches_table.setColumnCount(len(headers))
            self.ui.matches_table.setHorizontalHeaderLabels(headers)
            self.ui.matches_table.setSortingEnabled(False)
            self.ui.matches_table.insertRow(0)
            for column_index, header in enumerate(headers):
                if header.replace(' ', '_').lower() in message:
                    item = QTableWidgetItem(message[header.replace(' ', '_').lower()])
                    item.setBackground(message['color'])
                    item.setFlags(Qt.ItemIsEnabled)
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    self.ui.matches_table.setItem(0, column_index, item)
            self.ui.matches_table.horizontalHeader().setResizeMode(QtGui.QHeaderView.ResizeToContents)

        def get_fills(self):
            request = QNetworkRequest()
            url = 'https://api.exchange.coinbase.com/fills'
            path_url = '/fills'
            timestamp = str(time.time())
            message = timestamp + 'GET' + path_url
            message = message.encode('utf-8')
            hmac_key = base64.b64decode(COINBASE_EXCHANGE_API_SECRET)
            signature = hmac.new(hmac_key, message, hashlib.sha256)
            signature_b64 = base64.b64encode(signature.digest())
            request.setRawHeader('CB-ACCESS-SIGN', signature_b64)
            request.setRawHeader('CB-ACCESS-TIMESTAMP', timestamp)
            request.setRawHeader('CB-ACCESS-KEY', COINBASE_EXCHANGE_API_KEY)
            request.setRawHeader('CB-ACCESS-PASSPHRASE', COINBASE_EXCHANGE_API_PASSPHRASE)
            request.setUrl(QUrl(url))
            response = self.manager.get(request)
            response.finished.connect(self.process_fills)

        def process_fills(self):
            reply = self.sender()
            raw = reply.readAll()
            response = json.loads(raw.data().decode('utf-8'))
            for fill in response:
                self.add_fill(fill)

        def add_fill(self, message):
            alpha = min(255, int(20.0 * math.sqrt(float(message['size']))) + 20)
            message['value'] = '{0:,.2f}'.format(float(message['price']) * float(message['size']))
            message['price'] = '{0:,.2f}'.format(float(message['price']))
            message['size'] = '{0:,.4f}'.format(float(message['size']))
            message['time'] = parse(message['created_at']).astimezone(tzlocal()).strftime('%m-%d %H:%M:%S')
            if message['side'] == 'sell':
                message['color'] = QColor(255, 0, 0, alpha)
            else:
                message['color'] = QColor(0, 255, 0, alpha)
            self.matches += [message]
            headers = ['Price', 'Size', 'Value', 'Time']
            self.ui.fills_table.setColumnCount(len(headers))
            self.ui.fills_table.setHorizontalHeaderLabels(headers)
            self.ui.fills_table.setSortingEnabled(False)
            self.ui.fills_table.insertRow(0)
            for column_index, header in enumerate(headers):
                if header.replace(' ', '_').lower() in message:
                    item = QTableWidgetItem(message[header.replace(' ', '_').lower()])
                    item.setBackground(message['color'])
                    item.setFlags(Qt.ItemIsEnabled)
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    self.ui.fills_table.setItem(0, column_index, item)
            header = self.ui.fills_table.horizontalHeader()
            header.setResizeMode(QHeaderView.ResizeToContents)

        def get_open_orders(self):
            request = QNetworkRequest()
            url = 'https://api.exchange.coinbase.com/orders'
            path_url = '/orders'
            timestamp = str(time.time())
            message = timestamp + 'GET' + path_url
            message = message.encode('utf-8')
            hmac_key = base64.b64decode(COINBASE_EXCHANGE_API_SECRET)
            signature = hmac.new(hmac_key, message, hashlib.sha256)
            signature_b64 = base64.b64encode(signature.digest())
            request.setRawHeader('CB-ACCESS-SIGN', signature_b64)
            request.setRawHeader('CB-ACCESS-TIMESTAMP', timestamp)
            request.setRawHeader('CB-ACCESS-KEY', COINBASE_EXCHANGE_API_KEY)
            request.setRawHeader('CB-ACCESS-PASSPHRASE', COINBASE_EXCHANGE_API_PASSPHRASE)
            request.setUrl(QUrl(url))
            response = self.manager.get(request)
            response.finished.connect(self.process_open_orders)

        def process_open_orders(self):
            reply = self.sender()
            raw = reply.readAll()
            response = json.loads(raw.data().decode('utf-8'))
            for order in response:
                self.add_order(order)

        def add_order(self, message):
            alpha = min(255, int(20.0 * math.sqrt(float(message['size']))) + 20)
            message['value'] = '{0:,.2f}'.format(float(message['price']) * float(message['size']))
            message['price'] = '{0:,.2f}'.format(float(message['price']))
            message['size'] = '{0:,.4f}'.format(float(message['size']))
            message['time'] = parse(message['created_at']).astimezone(tzlocal()).strftime('%m-%d %H:%M:%S')
            if message['side'] == 'sell':
                message['color'] = QColor(255, 0, 0, alpha)
            else:
                message['color'] = QColor(0, 255, 0, alpha)
            self.matches += [message]
            headers = ['Price', 'Size', 'Value', 'Time']
            self.ui.open_orders_table.setColumnCount(len(headers))
            self.ui.open_orders_table.setHorizontalHeaderLabels(headers)
            self.ui.open_orders_table.setSortingEnabled(False)
            self.ui.open_orders_table.insertRow(0)
            for column_index, header in enumerate(headers):
                if header.replace(' ', '_').lower() in message:
                    item = QTableWidgetItem(message[header.replace(' ', '_').lower()])
                    item.setBackground(message['color'])
                    item.setFlags(Qt.ItemIsEnabled)
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    self.ui.open_orders_table.setItem(0, column_index, item)
            header = self.ui.open_orders_table.horizontalHeader()
            header.setResizeMode(QHeaderView.ResizeToContents)

        def start_websocket(self):
            thread = ListenWebsocket()
            self.connect(thread, thread.match_signal, self.add_match)
            self.connect(thread, thread.message_signal, self.process_message)
            self.connect(thread, thread.sequence_signal, self.update_sequence)
            self.connect(thread, thread.restart_signal, self.start_websocket)
            thread.start()

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
        self.sequence_signal = SIGNAL('sequence_signal')
        self.match_signal = SIGNAL('match_signal')
        self.restart_signal = SIGNAL('restart_signal')
        self.message_signal = SIGNAL('message_signal')
        self.WS = websocket.WebSocketApp('wss://ws-feed.exchange.coinbase.com',
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close)

    def run(self):
        self.WS.on_open = self.on_open
        self.WS.run_forever()

    def on_open(self, ws):
        self.WS.send('{"type": "subscribe", "product_id": "BTC-USD"}')

    def on_message(self, ws, message):
        if message is None:
            print('empty message')
            self.emit(self.restart_signal)
            self.exit(0)
        message = json.loads(message)
        self.emit(self.message_signal, message)
        self.emit(self.sequence_signal, message['sequence'])
        if message['type'] == 'match':
            self.emit(self.match_signal, message)

    def on_error(self, ws, error):
        print('Error: ' + str(error))
        self.emit(self.restart_signal)
        self.exit(0)

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
