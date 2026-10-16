"""Regression coverage for the port's persistence and service adapter."""
import asyncio
import copy
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'budget_book/rootfs/app'))
import analytics
import server
from persistence import normalize_data
from store import BudgetStore


class AddonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'ledger.json')
        server.STORE = BudgetStore(self.path)
        asyncio.run(server.STORE.async_load())

    def call(self, service, **data):
        asyncio.run(server.dispatch(service, data))

    @property
    def book(self):
        return server.STORE.active_book

    def test_transactions_and_metrics_survive_restart(self):
        tx = dict(date=date.today().isoformat(), time='13:45', type='expense', amount=350, category='food', note='Lunch')
        self.call('add_transaction', **tx)
        tid = self.book['transactions'][0]['id']
        self.call('update_transaction', transaction_id=tid, **{**tx, 'amount': 420})
        self.assertEqual(server.snapshot()['sensor.budget_book_month_expense']['state'], 420)
        server.STORE = BudgetStore(self.path)
        asyncio.run(server.STORE.async_load())
        self.assertEqual(self.book['transactions'][0]['time'], '13:45')
        self.assertEqual(self.book['transactions'][0]['amount'], 420)
        self.call('delete_transaction', transaction_id=tid)
        self.assertEqual(self.book['transactions'], [])

    def test_book_management(self):
        original = self.book['id']
        self.call('create_book', name='Travel', currency='USD')
        bid = next(bid for bid in server.STORE.books if bid != original)
        self.call('rename_book', book_id=bid, name='Holiday')
        self.call('set_active_book', book_id=bid)
        self.assertEqual(self.book['name'], 'Holiday')
        self.assertEqual(self.book['currency'], 'USD')
        self.call('delete_book', book_id=bid)
        self.assertEqual(self.book['id'], original)
        with self.assertRaises(ValueError):
            self.call('delete_book', book_id=original)

    def test_categories_budgets_and_reassignment(self):
        self.call('add_category', name='Pets', type='expense', icon='mdi:tag', color='#123456')
        cid = self.book['categories'][-1]['id']
        self.call('set_budget', category=cid, amount=100)
        self.call('add_transaction', date=date.today().isoformat(), type='expense', amount=120, category=cid)
        self.assertEqual(server.snapshot()['sensor.budget_book_over_budget_count']['state'], 1)
        self.call('delete_category', category=cid)
        self.assertNotIn(cid, self.book['budgets'])
        self.assertEqual(self.book['transactions'][0]['category'], 'other')
        self.call('set_budget', category='food', amount=500)
        self.call('set_budget', category='food', amount=None)
        self.assertNotIn('food', self.book['budgets'])

    def test_recurring_idempotent_across_restart(self):
        self.call('add_recurring', name='Rent', type='expense', amount=12000, category='rent', day_of_month=1)
        rid = self.book['recurring'][0]['id']
        self.call('run_recurring')
        server.STORE = BudgetStore(self.path)
        asyncio.run(server.STORE.async_load())
        self.call('run_recurring')
        self.assertEqual(len(self.book['transactions']), 1)
        self.assertEqual(self.book['transactions'][0]['recurring_id'], rid)
        self.call('delete_recurring', recurring_id=rid)
        self.assertEqual(self.book['recurring'], [])

    def test_recurring_end_of_month_falls_back_to_last_day(self):
        book = {'recurring': [{'id': 'r31', 'name': 'Salary', 'amount': 1, 'type': 'income',
                               'category': 'salary', 'day_of_month': 31, 'active': True}]}
        cases = [
            (date(2026, 1, 30), False), (date(2026, 1, 31), True),
            (date(2026, 2, 27), False), (date(2026, 2, 28), True),
            (date(2028, 2, 28), False), (date(2028, 2, 29), True),
            (date(2026, 4, 29), False), (date(2026, 4, 30), True),
        ]
        for today, expected in cases:
            with self.subTest(today=today):
                self.assertEqual(bool(analytics.find_due_recurring(book, today)), expected)

        book['recurring'][0]['day_of_month'] = 30
        self.assertFalse(analytics.find_due_recurring(book, date(2026, 1, 29)))
        self.assertTrue(analytics.find_due_recurring(book, date(2026, 2, 28)))

        # Upcoming due date uses the target month's last day, including across years.
        book['recurring'][0]['day_of_month'] = 31
        def upcoming(today):
            return analytics.compute_book_metrics(book, today)['recurring_upcoming'][0]['due_date']
        self.assertEqual(upcoming(date(2026, 2, 10)), '2026-02-28')
        self.assertEqual(upcoming(date(2026, 3, 31)), '2026-03-31')
        self.assertEqual(upcoming(date(2026, 4, 1)), '2026-04-30')
        self.assertEqual(upcoming(date(2028, 1, 31)), '2028-01-31')
        self.assertEqual(upcoming(date(2026, 12, 15)), '2026-12-31')
        book['recurring'][0]['day_of_month'] = 29
        self.assertEqual(upcoming(date(2026, 1, 30)), '2026-02-28')
        self.assertEqual(upcoming(date(2028, 1, 30)), '2028-02-29')

    def test_import_export_sample_and_clear(self):
        self.call('load_sample')
        exported = copy.deepcopy(server.STORE.data)
        self.assertTrue(self.book['transactions'])
        self.call('clear_all')
        self.assertEqual(self.book['transactions'], [])
        self.call('replace_data', data=exported)
        self.assertEqual(server.STORE.data, exported)
        self.assertEqual(normalize_data({'version': 1, 'data': exported}), exported)

    def test_invalid_import_preserves_data(self):
        before = copy.deepcopy(server.STORE.data)
        for bad in ({}, {'books': {}}, {'books': {'x': {}}}):
            with self.assertRaises((ValueError, KeyError)):
                self.call('replace_data', data=bad)
        self.assertEqual(server.STORE.data, before)

    def test_bad_amount_and_recurring_day(self):
        for invalid in (-1, float('inf'), float('nan')):
            with self.assertRaises(ValueError):
                self.call('add_transaction', date='2026-10-12', type='expense', amount=invalid)
        with self.assertRaises(ValueError):
            self.call('add_recurring', name='Bad', amount=1, day_of_month=32)

    def test_scaffold_migration_keeps_backup(self):
        old = {'books': [{'id': 'default', 'name': 'Default', 'currency': 'TWD',
                         'transactions': [{'id': 'tx1', 'date': '2026-10-12', 'type': 'expense', 'amount': 10, 'category': 'Food'}],
                         'categories': {'expense': ['Food'], 'income': ['Salary']}, 'budgets': {}}],
               'active_book_id': 'default'}
        Path(self.path).write_text(json.dumps(old))
        migrated = BudgetStore(self.path)
        asyncio.run(migrated.async_load())
        self.assertEqual(migrated.active_book['transactions'][0]['amount'], 10)
        self.assertEqual(migrated.active_book['recurring'], [])
        self.assertEqual(json.loads(Path(self.path).with_suffix('.json.pre-migration').read_text()), old)

    def test_corrupt_storage_is_not_overwritten(self):
        Path(self.path).write_text('broken')
        with self.assertRaises(ValueError):
            asyncio.run(BudgetStore(self.path).async_load())
        self.assertEqual(Path(self.path).read_text(), 'broken')

    def test_ha_sensors_match_integration_entities(self):
        self.call('add_transaction', date=date.today().isoformat(), type='expense', amount=200, category='food')
        self.call('set_budget', category='food', amount=100)
        states = server.ha_sensor_states()
        self.assertEqual(states['sensor.budget_book_month_expense'][0], 200)
        self.assertEqual(states['sensor.budget_book_over_budget_count'][0], 1)
        self.assertEqual(states['sensor.budget_book_active_book'][0], self.book['name'])
        self.assertNotIn('full_data', states['sensor.budget_book_all_books'][1])
        json.dumps(states)

    def test_startup_sync_pushes_existing_addon_data_to_empty_integration(self):
        integration_data = copy.deepcopy(server.STORE.data)
        self.call('add_transaction', date=date.today().isoformat(), type='expense', amount=200, category='food')
        pushed = []

        original_fetch = server.fetch_integration_data
        original_push = server.push_data_to_integration
        try:
            server.fetch_integration_data = lambda: integration_data
            server.push_data_to_integration = lambda data=None: pushed.append(copy.deepcopy(data or server.STORE.data)) or True
            asyncio.run(server.sync_with_integration_on_start())
        finally:
            server.fetch_integration_data = original_fetch
            server.push_data_to_integration = original_push

        self.assertEqual(pushed[0], server.STORE.data)
        self.assertEqual(server.STORE.active_book['transactions'][0]['amount'], 200)

    def test_startup_sync_uses_integration_data_and_preserves_addon_backup_on_conflict(self):
        self.call('add_transaction', date=date.today().isoformat(), type='expense', amount=200, category='food')
        addon_before = copy.deepcopy(server.STORE.data)
        self.call('load_sample')
        integration_data = copy.deepcopy(server.STORE.data)
        server.STORE = BudgetStore(self.path)
        asyncio.run(server.STORE.async_load())
        asyncio.run(server.STORE.async_replace_data(addon_before))

        original_fetch = server.fetch_integration_data
        try:
            server.fetch_integration_data = lambda: integration_data
            asyncio.run(server.sync_with_integration_on_start())
        finally:
            server.fetch_integration_data = original_fetch

        self.assertEqual(server.STORE.data, integration_data)
        backups = list(Path(self.path).parent.glob('ledger.json.pre-ha-sync-*'))
        self.assertTrue(backups)
        self.assertEqual(json.loads(backups[0].read_text()), addon_before)

    def test_refresh_pulls_direct_integration_changes_while_addon_is_running(self):
        integration_data = copy.deepcopy(server.STORE.data)
        book_id = integration_data['active_book_id']
        integration_data['books'][book_id]['transactions'].append({
            'id': 'haedit',
            'date': date.today().isoformat(),
            'time': None,
            'type': 'expense',
            'amount': 88,
            'category': 'food',
            'note': 'edited in integration',
            'recurring_id': None,
        })

        original_fetch = server.fetch_integration_data
        try:
            server.fetch_integration_data = lambda: integration_data
            changed = asyncio.run(server.refresh_from_integration_source())
        finally:
            server.fetch_integration_data = original_fetch

        self.assertTrue(changed)
        self.assertEqual(server.STORE.active_book['transactions'][0]['id'], 'haedit')


if __name__ == '__main__':
    unittest.main()
