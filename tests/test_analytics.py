"""Recurring date rules, checked against every shipped copy of analytics.py."""
import importlib.util
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPIES = {
    'shared': ROOT / 'shared/core/analytics.py',
    'hacs': ROOT / 'custom_components/budget_book/analytics.py',
    'addon': ROOT / 'budget_book/rootfs/app/analytics.py',
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(f'budget_book_analytics_{name}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def book_with_day(day):
    return {'recurring': [{'id': 'r', 'name': 'Salary', 'amount': 1, 'type': 'income',
                           'category': 'salary', 'day_of_month': day, 'active': True}]}


class RecurringDateTests(unittest.TestCase):
    def each_copy(self):
        for name, path in COPIES.items():
            with self.subTest(copy=name):
                yield load(name, path)

    def test_copies_are_in_sync(self):
        shared = COPIES['shared'].read_text()
        for name in ('hacs', 'addon'):
            self.assertEqual(COPIES[name].read_text(), shared,
                             f'{name} analytics.py is stale; run scripts/sync_shared_core.py')

    def test_due_falls_back_to_last_day_of_shorter_months(self):
        cases = [
            (31, date(2026, 1, 30), False), (31, date(2026, 1, 31), True),
            (31, date(2026, 2, 27), False), (31, date(2026, 2, 28), True),
            (31, date(2028, 2, 28), False), (31, date(2028, 2, 29), True),
            (31, date(2026, 4, 29), False), (31, date(2026, 4, 30), True),
            (30, date(2026, 1, 29), False), (30, date(2026, 2, 28), True),
            (15, date(2026, 2, 14), False), (15, date(2026, 2, 15), True),
        ]
        for analytics in self.each_copy():
            for day, today, expected in cases:
                with self.subTest(day=day, today=today):
                    self.assertEqual(bool(analytics.find_due_recurring(book_with_day(day), today)), expected)

    def test_already_run_this_month_is_not_due(self):
        book = book_with_day(31)
        book['recurring'][0]['last_run_date'] = '2026-02-28'
        for analytics in self.each_copy():
            self.assertFalse(analytics.find_due_recurring(book, date(2026, 2, 28)))
            self.assertTrue(analytics.find_due_recurring(book, date(2026, 3, 31)))

    def test_upcoming_due_date_uses_target_month_length(self):
        cases = [
            (31, date(2026, 2, 10), '2026-02-28'),
            (31, date(2026, 3, 31), '2026-03-31'),
            (31, date(2026, 4, 1), '2026-04-30'),
            (31, date(2028, 1, 31), '2028-01-31'),
            (31, date(2026, 12, 15), '2026-12-31'),
            (15, date(2026, 12, 16), '2027-01-15'),
            (29, date(2026, 1, 30), '2026-02-28'),
            (29, date(2028, 1, 30), '2028-02-29'),
        ]
        for analytics in self.each_copy():
            for day, today, expected in cases:
                with self.subTest(day=day, today=today):
                    upcoming = analytics.compute_book_metrics(book_with_day(day), today)['recurring_upcoming'][0]
                    self.assertEqual(upcoming['due_date'], expected)


if __name__ == '__main__':
    unittest.main()
