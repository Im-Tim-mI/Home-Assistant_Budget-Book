"""Supervisor HTTP adapter for the original Budget Book store and analytics."""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import os
import re
import threading
import urllib.request
import uuid
from datetime import date, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from analytics import compute_book_metrics, find_due_recurring
from persistence import normalize_data
from sample_data import build_sample
from store import BudgetStore

HOST = os.environ.get('BUDGET_BOOK_HOST', '0.0.0.0')
PORT = int(os.environ.get('BUDGET_BOOK_PORT', '8099'))
WEB_ROOT = Path(os.environ.get('BUDGET_BOOK_WEB_ROOT', str(Path(__file__).parent / 'www')))
LOCK = threading.RLock()
STORE = BudgetStore(os.environ.get('BUDGET_BOOK_DATA', '/data/budget_book.json'))


async def run_recurring():
    today = date.today()
    # Insert transactions and mark rules in one persisted update.
    data = copy.deepcopy(STORE.data)
    changed = False
    for book in data['books'].values():
        for rule in find_due_recurring(book, today):
            book['transactions'].append({
                'id': uuid.uuid4().hex[:12], 'date': today.isoformat(), 'time': None,
                'type': rule['type'], 'amount': rule['amount'], 'category': rule['category'],
                'note': f"[固定] {rule['name']}", 'recurring_id': rule['id'],
            })
            rule['last_run_date'] = today.isoformat()
            changed = True
    if changed:
        await STORE.async_replace_data(data)


def snapshot():
    metrics = compute_book_metrics(STORE.active_book) if STORE.active_book else {}
    states = {f'sensor.budget_book_{key}': {'state': value, 'attributes': {}}
              for key, value in metrics.items()}
    states['sensor.budget_book_month_expense']['attributes'] = metrics
    states['sensor.budget_book_all_books'] = {
        'state': len(STORE.books), 'attributes': {'full_data': STORE.data}}
    return states


SENSORS = [
    # key, friendly name, unit (None = book currency), icon, state_class
    ('month_expense', '本月支出', None, 'mdi:cash-minus', 'measurement'),
    ('month_income', '本月收入', None, 'mdi:cash-plus', 'measurement'),
    ('month_balance', '本月結餘', None, 'mdi:scale-balance', 'measurement'),
    ('balance', '總結餘', None, 'mdi:wallet', 'measurement'),
    ('transaction_count', '總交易筆數', '筆', 'mdi:counter', 'total_increasing'),
    ('over_budget_count', '預算超支類別數', '個', 'mdi:alert', 'measurement'),
]
SENSOR_DIRTY = threading.Event()


def ha_sensor_states():
    """Mirror the integration's sensor entities for automations."""
    book = STORE.active_book
    metrics = compute_book_metrics(book) if book else {}
    currency = book.get('currency', 'TWD') if book else 'TWD'
    states = {}
    for key, name, unit, icon, state_class in SENSORS:
        attrs = {'friendly_name': name, 'icon': icon, 'state_class': state_class,
                 'unit_of_measurement': unit or currency}
        if key == 'month_expense':
            attrs.update({k: metrics.get(k) for k in ('month_label', 'this_month_count', 'category_breakdown', 'budget_alerts')})
        elif key == 'over_budget_count':
            attrs['alerts'] = metrics.get('budget_alerts', [])
        states[f'sensor.budget_book_{key}'] = (metrics.get(key, 0), attrs)
    attrs = {'friendly_name': '目前記帳本', 'icon': 'mdi:notebook'}
    if book:
        attrs.update({
            'book_id': book['id'], 'currency': currency,
            'transaction_count': len(book.get('transactions', [])),
            'category_count': len(book.get('categories', [])),
            'recurring_count': len(book.get('recurring', [])),
            'budget_count': len(book.get('budgets', {})),
        })
    states['sensor.budget_book_active_book'] = (book['name'] if book else 'unknown', attrs)
    # full_data stays in the add-on; HA state attributes are size-limited.
    states['sensor.budget_book_all_books'] = (len(STORE.books), {
        'friendly_name': '所有記帳本', 'icon': 'mdi:book-multiple', 'unit_of_measurement': '本',
        'books': [{'id': b['id'], 'name': b['name'], 'currency': b.get('currency', 'TWD'),
                   'transaction_count': len(b.get('transactions', []))} for b in STORE.books.values()],
        'active_book_id': STORE.data.get('active_book_id'),
    })
    return states


def publish_sensors():
    token = os.environ.get('SUPERVISOR_TOKEN')
    if not token:
        return
    with LOCK:
        states = ha_sensor_states()
    for entity_id, (state, attrs) in states.items():
        body = json.dumps({'state': state, 'attributes': attrs}, ensure_ascii=False).encode()
        request = urllib.request.Request(
            f'http://supervisor/core/api/states/{entity_id}', data=body, method='POST',
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
        urllib.request.urlopen(request, timeout=10).close()


def sensor_publisher(stop):
    # Republish periodically too: HA drops API-created states on restart.
    while not stop.is_set():
        SENSOR_DIRTY.wait(300)
        SENSOR_DIRTY.clear()
        try:
            publish_sensors()
        except Exception as error:
            logging.warning('Publishing sensors to Home Assistant failed: %s', error)


def amount(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('Amount must be finite and non-negative')
    return value


async def dispatch(service, payload):
    data = dict(payload)
    bid = data.pop('book_id', None) or STORE.data['active_book_id']
    if bid not in STORE.books and service != 'create_book':
        raise ValueError('Book not found')
    if service in ('add_transaction', 'update_transaction', 'add_recurring'):
        if data.get('type', 'expense') not in ('income', 'expense'):
            raise ValueError('Invalid transaction type')
        data['amount'] = amount(data['amount'])
        if service != 'add_recurring':
            if data.get('time') and not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', data['time']):
                raise ValueError('Invalid time')
        else:
            data['day_of_month'] = int(data['day_of_month'])
            if not 1 <= data['day_of_month'] <= 31:
                raise ValueError('Invalid recurring day')
    if service == 'add_transaction':
        await STORE.async_add_transaction(bid, data)
    elif service == 'update_transaction':
        await STORE.async_update_transaction(bid, data.pop('transaction_id'), data)
    elif service == 'delete_transaction':
        await STORE.async_delete_transaction(bid, data['transaction_id'])
    elif service == 'create_book':
        await STORE.async_create_book(data['name'], data.get('currency', 'TWD'))
    elif service == 'delete_book':
        await STORE.async_delete_book(bid)
    elif service == 'rename_book':
        await STORE.async_rename_book(bid, data['name'])
    elif service == 'set_active_book':
        await STORE.async_set_active_book(bid)
    elif service == 'set_budget':
        await STORE.async_set_budget(bid, data['category'], None if data.get('amount') is None else amount(data['amount']))
    elif service == 'add_category':
        await STORE.async_add_category(bid, data['name'], data['type'], data.get('icon'), data.get('color'))
    elif service == 'delete_category':
        await STORE.async_delete_category(bid, data['category'])
    elif service == 'add_recurring':
        await STORE.async_add_recurring(bid, data)
    elif service == 'delete_recurring':
        await STORE.async_delete_recurring(bid, data['recurring_id'])
    elif service == 'run_recurring':
        await run_recurring()
    elif service == 'load_sample':
        await STORE.async_replace_data(build_sample())
    elif service == 'clear_all':
        await STORE.async_clear_active_book_data()
    elif service == 'replace_data':
        await STORE.async_replace_data(normalize_data(data['data']))
    else:
        raise ValueError('Unknown service')


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/api/states', '/api/data', '/api/export', '/api/health'):
            with LOCK:
                result = {'status': 'ok'} if path == '/api/health' else snapshot() if path == '/api/states' else STORE.data
                self.send_json(200, result)
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        prefix = '/api/services/budget_book/'
        if not path.startswith(prefix):
            self.send_json(404, {'error': 'Not found'})
            return
        try:
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('Expected application/json')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 20 * 1024 * 1024:
                raise ValueError('Invalid request size (limit 20 MiB)')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected an object')
            with LOCK:
                before = copy.deepcopy(STORE.data)
                try:
                    asyncio.run(dispatch(path[len(prefix):], data))
                except Exception:
                    STORE._data = before
                    raise
                SENSOR_DIRTY.set()
                self.send_json(200, snapshot())
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
            self.send_json(400, {'error': str(error)})
        except OSError:
            logging.exception('Persistence failed')
            self.send_json(500, {'error': 'Unable to persist data'})


def recurring_scheduler(stop):
    last_day = None
    while not stop.is_set():
        now = datetime.now()
        if last_day != now.date() and now.hour >= 9:
            try:
                with LOCK:
                    asyncio.run(run_recurring())
                last_day = now.date()
                SENSOR_DIRTY.set()
            except Exception:
                logging.exception('Recurring check failed; will retry')
        stop.wait(30)


if __name__ == '__main__':
    level = os.environ.get('BUDGET_BOOK_LOG_LEVEL', 'info').upper()
    level = {'TRACE': 'DEBUG', 'NOTICE': 'INFO', 'FATAL': 'CRITICAL'}.get(level, level)
    logging.basicConfig(level=getattr(logging, level, logging.INFO))
    asyncio.run(STORE.async_load())
    asyncio.run(run_recurring())
    stop = threading.Event()
    threading.Thread(target=recurring_scheduler, args=(stop,), daemon=True).start()
    SENSOR_DIRTY.set()
    threading.Thread(target=sensor_publisher, args=(stop,), daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
