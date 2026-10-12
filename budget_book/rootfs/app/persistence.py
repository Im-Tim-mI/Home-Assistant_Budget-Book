"""Atomic /data persistence adapter for the original BudgetStore."""
import copy
import json
import math
import os
import shutil
from datetime import datetime
from pathlib import Path


def normalize_data(value):
    from store import make_default_book

    data = copy.deepcopy(value)
    if not isinstance(data, dict):
        raise ValueError('Expected a JSON object')
    if 'books' not in data and isinstance(data.get('data'), dict):
        data = data['data']
    books = data.get('books')
    if isinstance(books, list):
        # Preserve transactions from the previous 0.1.0 scaffold.
        converted = {}
        for old in books:
            book = make_default_book(old.get('name', 'Budget Book'), old.get('currency', 'TWD'))
            book.update(old)
            categories = old.get('categories', {})
            if isinstance(categories, dict):
                book['categories'] = [
                    {'id': name, 'name': name, 'type': kind, 'icon': 'mdi:tag', 'color': '#95A5A6'}
                    for kind, names in categories.items() for name in names
                ]
            converted[book['id']] = book
        data['books'] = books = converted
    if not isinstance(books, dict) or not books:
        raise ValueError('At least one book is required')
    for bid, book in books.items():
        if not isinstance(book, dict) or book.get('id') != bid or not isinstance(book.get('name'), str):
            raise ValueError('Invalid book')
        for key in ('transactions', 'categories', 'recurring'):
            book.setdefault(key, [])
            if not isinstance(book[key], list):
                raise ValueError('Invalid ' + key)
        book.setdefault('budgets', {})
        if not isinstance(book['budgets'], dict):
            raise ValueError('Invalid budgets')
        for amount in book['budgets'].values():
            if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
                raise ValueError('Invalid budget amount')
        for category in book['categories']:
            if not all(isinstance(category.get(k), str) for k in ('id', 'name', 'type')) or category['type'] not in ('income', 'expense'):
                raise ValueError('Invalid category')
        for key in ('transactions', 'recurring'):
            ids = set()
            for item in book[key]:
                if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in ids:
                    raise ValueError('Invalid or duplicate record ID')
                ids.add(item['id'])
                if item.get('type') not in ('income', 'expense') or not isinstance(item.get('category'), str):
                    raise ValueError('Invalid record type or category')
                amount = item.get('amount')
                if not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
                    raise ValueError('Invalid record amount')
                if key == 'transactions':
                    datetime.strptime(item['date'], '%Y-%m-%d')
                elif not isinstance(item.get('day_of_month'), int) or not 1 <= item['day_of_month'] <= 31:
                    raise ValueError('Invalid recurring day')
    if data.get('active_book_id') not in books:
        data['active_book_id'] = next(iter(books))
    return data


class Store:
    def __init__(self, path):
        self.path = Path(path)

    async def async_load(self):
        if not self.path.exists():
            return None
        # Never replace an unreadable ledger with an empty one.
        original = json.loads(self.path.read_text(encoding='utf-8'))
        data = normalize_data(original)
        if data != original:
            backup = self.path.with_suffix('.json.pre-migration')
            if not backup.exists():
                shutil.copy2(self.path, backup)
            await self.async_save(data)
        return data

    async def async_save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.json.tmp')
        with tmp.open('w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, allow_nan=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(self.path)
