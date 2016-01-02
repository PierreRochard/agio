from datetime import datetime
from decimal import Decimal

try:
    import ujson as json
except ImportError:
    import json
import pytz

from order_book.tree import Tree


class Book(object):
    def __init__(self):
        self.bids = Tree()
        self.asks = Tree()

        self.level3_sequence = 0
        self.first_sequence = 0
        self.last_sequence = 0

    def process_message(self, message):

        new_sequence = int(message['sequence'])
        # if new_sequence <= self.last_sequence:
        #     return True
        #
        # if new_sequence <= self.level3_sequence:
        #     return True
        #
        # if not self.first_sequence:
        #     self.first_sequence = new_sequence
        #     self.last_sequence = new_sequence
        #     assert new_sequence - self.level3_sequence == 1
        # else:
        #     if (new_sequence - self.last_sequence) != 1:
        #         return False
        #     self.last_sequence = new_sequence

        if 'order_type' in message and message['order_type'] == 'market':
            return True

        message_type = message['type']
        side = message['side']
        message['time'] = datetime.strptime(message['time'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=pytz.UTC)

        if message_type == 'received' and side == 'buy':
            self.bids.receive(message['order_id'], message['size'])
            return True
        elif message_type == 'received' and side == 'sell':
            self.asks.receive(message['order_id'], message['size'])
            return True

        elif message_type == 'open' and side == 'buy':
            self.bids.insert_order(message['order_id'], Decimal(message['remaining_size']), Decimal(message['price']))
            return True
        elif message_type == 'open' and side == 'sell':
            self.asks.insert_order(message['order_id'], Decimal(message['remaining_size']), Decimal(message['price']))
            return True

        elif message_type == 'match' and side == 'buy':
            self.bids.match(message['maker_order_id'], Decimal(message['size']))
            return True

        elif message_type == 'match' and side == 'sell':
            self.asks.match(message['maker_order_id'], Decimal(message['size']))
            return True

        elif message_type == 'done' and side == 'buy':
            self.bids.remove_order(message['order_id'])
            return True
        elif message_type == 'done' and side == 'sell':
            self.asks.remove_order(message['order_id'])
            return True

        elif message_type == 'change' and side == 'buy':
            self.bids.change(message['order_id'], Decimal(message['new_size']))
            return True
        elif message_type == 'change' and side == 'sell':
            self.asks.change(message['order_id'], Decimal(message['new_size']))
            return True

        else:
            return False
