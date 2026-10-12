"""Sample data for first-run / load_sample."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from .const import DEFAULT_EXPENSE_CATEGORIES, DEFAULT_INCOME_CATEGORIES


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def build_sample() -> dict:
    """Build a complete sample dataset with two demo books."""
    today = date.today()

    def cats():
        result = []
        for c in DEFAULT_INCOME_CATEGORIES:
            result.append({**c, "type": "income"})
        for c in DEFAULT_EXPENSE_CATEGORIES:
            result.append({**c, "type": "expense"})
        return result

    # Book 1: Daily life
    book1_id = _gen_id()
    book1_txs = []
    # Last 60 days of varied transactions
    samples = [
        (0, "expense", 95, "food", "便利商店午餐"),
        (1, "expense", 320, "food", "晚餐聚會"),
        (2, "expense", 60, "transport", "捷運"),
        (3, "expense", 1280, "shopping", "新衣服"),
        (5, "expense", 158, "food", "麥當勞"),
        (7, "expense", 850, "entertainment", "電影 + 爆米花"),
        (10, "income", 65000, "salary", "5月薪資"),
        (10, "expense", 18000, "rent", "5月房租"),
        (10, "expense", 390, "subscription", "Netflix + Spotify"),
        (12, "expense", 1450, "food", "週末聚餐"),
        (14, "expense", 245, "household", "洗衣精"),
        (16, "expense", 88, "food", "早餐店"),
        (18, "expense", 520, "medical", "感冒看診"),
        (20, "expense", 2100, "utility", "電費水費"),
        (22, "expense", 175, "transport", "計程車"),
        (25, "expense", 680, "food", "晚餐"),
        (27, "expense", 3200, "shopping", "鞋子"),
        (30, "expense", 110, "food", "午餐"),
        (33, "expense", 1850, "entertainment", "演唱會門票"),
        (35, "income", 3000, "side", "兼差收入"),
        (38, "expense", 420, "food", "週末市場採購"),
        (42, "expense", 60, "transport", "公車"),
        (45, "expense", 290, "shopping", "日用品"),
        (50, "expense", 78, "food", "飲料"),
        (55, "expense", 1100, "subscription", "雲端空間年費"),
    ]
    for days_ago, t_type, amount, cat, note in samples:
        d = today - timedelta(days=days_ago)
        book1_txs.append({
            "id": _gen_id(),
            "date": d.isoformat(),
            "type": t_type,
            "amount": float(amount),
            "category": cat,
            "note": note,
            "recurring_id": None,
        })

    book1 = {
        "id": book1_id,
        "name": "日常開銷",
        "currency": "TWD",
        "created_at": today.isoformat(),
        "transactions": book1_txs,
        "categories": cats(),
        "budgets": {
            "food": 8000,
            "transport": 1500,
            "entertainment": 3000,
            "shopping": 5000,
            "subscription": 800,
        },
        "recurring": [
            {
                "id": _gen_id(),
                "name": "房租",
                "type": "expense",
                "amount": 18000,
                "category": "rent",
                "day_of_month": 5,
                "note": "每月房租自動扣款",
                "last_run_date": today.replace(day=1).isoformat() if today.day >= 5 else None,
                "active": True,
            },
            {
                "id": _gen_id(),
                "name": "Netflix",
                "type": "expense",
                "amount": 270,
                "category": "subscription",
                "day_of_month": 10,
                "note": "月費",
                "last_run_date": None,
                "active": True,
            },
            {
                "id": _gen_id(),
                "name": "Spotify",
                "type": "expense",
                "amount": 149,
                "category": "subscription",
                "day_of_month": 15,
                "note": "個人方案",
                "last_run_date": None,
                "active": True,
            },
        ],
    }

    # Book 2: Travel fund
    book2_id = _gen_id()
    book2_txs = []
    travel_samples = [
        (50, "income", 5000, "salary", "出差津貼"),
        (45, "expense", 1280, "food", "餐廳"),
        (40, "expense", 850, "transport", "高鐵"),
        (35, "income", 3000, "bonus", "旅遊基金"),
        (20, "expense", 2400, "entertainment", "景點門票"),
        (15, "expense", 980, "food", "當地小吃"),
    ]
    for days_ago, t_type, amount, cat, note in travel_samples:
        d = today - timedelta(days=days_ago)
        book2_txs.append({
            "id": _gen_id(),
            "date": d.isoformat(),
            "type": t_type,
            "amount": float(amount),
            "category": cat,
            "note": note,
            "recurring_id": None,
        })

    book2 = {
        "id": book2_id,
        "name": "旅遊基金",
        "currency": "TWD",
        "created_at": today.isoformat(),
        "transactions": book2_txs,
        "categories": cats(),
        "budgets": {},
        "recurring": [],
    }

    return {
        "books": {book1_id: book1, book2_id: book2},
        "active_book_id": book1_id,
    }
