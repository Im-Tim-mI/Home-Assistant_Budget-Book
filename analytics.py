"""Analytics computations for Budget Book."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def compute_book_metrics(book: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Compute headline metrics for the active book."""
    if today is None:
        today = date.today()
    txs = book.get("transactions", [])
    cats = {c["id"]: c for c in book.get("categories", [])}
    budgets = book.get("budgets", {})

    # All-time totals
    total_income = sum(t["amount"] for t in txs if t["type"] == "income")
    total_expense = sum(t["amount"] for t in txs if t["type"] == "expense")
    balance = total_income - total_expense

    # This month
    m_start, m_end = month_range(today.year, today.month)
    this_month_txs = [t for t in txs if m_start <= _parse_date(t["date"]) <= m_end]
    month_income = sum(t["amount"] for t in this_month_txs if t["type"] == "income")
    month_expense = sum(t["amount"] for t in this_month_txs if t["type"] == "expense")
    month_balance = month_income - month_expense

    # Per-category this month (expense only by default)
    month_by_category = defaultdict(lambda: {"amount": 0.0, "count": 0})
    for t in this_month_txs:
        if t["type"] == "expense":
            month_by_category[t["category"]]["amount"] += t["amount"]
            month_by_category[t["category"]]["count"] += 1

    category_breakdown = []
    for cat_id, agg in month_by_category.items():
        cat = cats.get(cat_id, {"name": cat_id, "icon": "mdi:tag", "color": "#95A5A6"})
        budget = budgets.get(cat_id)
        usage = (agg["amount"] / budget * 100) if budget and budget > 0 else None
        category_breakdown.append({
            "category_id": cat_id,
            "name": cat.get("name", cat_id),
            "icon": cat.get("icon"),
            "color": cat.get("color"),
            "amount": round(agg["amount"], 2),
            "count": agg["count"],
            "budget": budget,
            "usage_pct": round(usage, 1) if usage is not None else None,
        })
    category_breakdown.sort(key=lambda x: -x["amount"])

    # Last 6 months trend
    trend = []
    for offset in range(5, -1, -1):
        y = today.year
        m = today.month - offset
        while m <= 0:
            m += 12
            y -= 1
        s, e = month_range(y, m)
        m_txs = [t for t in txs if s <= _parse_date(t["date"]) <= e]
        trend.append({
            "year": y,
            "month": m,
            "label": f"{y}-{m:02d}",
            "income": round(sum(t["amount"] for t in m_txs if t["type"] == "income"), 2),
            "expense": round(sum(t["amount"] for t in m_txs if t["type"] == "expense"), 2),
        })

    # Budget alerts
    budget_alerts = []
    for cat_id, limit in budgets.items():
        if limit <= 0:
            continue
        spent = sum(
            t["amount"]
            for t in this_month_txs
            if t["type"] == "expense" and t["category"] == cat_id
        )
        pct = spent / limit * 100
        if pct >= 100:
            severity = "over"
        elif pct >= 80:
            severity = "warning"
        else:
            severity = "ok"
        cat = cats.get(cat_id, {"name": cat_id})
        budget_alerts.append({
            "category_id": cat_id,
            "category_name": cat.get("name", cat_id),
            "spent": round(spent, 2),
            "limit": limit,
            "pct": round(pct, 1),
            "severity": severity,
        })
    budget_alerts.sort(key=lambda x: -x["pct"])

    # Overall budget summary
    over_budget_count = sum(1 for a in budget_alerts if a["severity"] == "over")
    warn_budget_count = sum(1 for a in budget_alerts if a["severity"] == "warning")

    # Recurring upcoming
    recurring_upcoming = []
    for rule in book.get("recurring", []):
        if not rule.get("active", True):
            continue
        # Find next due date based on day_of_month
        day = min(rule["day_of_month"], 28)  # safe day
        # Try this month first
        try:
            due = date(today.year, today.month, day)
        except ValueError:
            due = m_end
        if due < today:
            # next month
            if today.month == 12:
                due = date(today.year + 1, 1, day)
            else:
                due = date(today.year, today.month + 1, day)
        days_until = (due - today).days
        recurring_upcoming.append({
            "id": rule["id"],
            "name": rule["name"],
            "amount": rule["amount"],
            "type": rule["type"],
            "category": rule["category"],
            "due_date": due.isoformat(),
            "days_until": days_until,
            "last_run_date": rule.get("last_run_date"),
        })
    recurring_upcoming.sort(key=lambda r: r["days_until"])

    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "balance": round(balance, 2),
        "month_income": round(month_income, 2),
        "month_expense": round(month_expense, 2),
        "month_balance": round(month_balance, 2),
        "month_label": f"{today.year}-{today.month:02d}",
        "transaction_count": len(txs),
        "this_month_count": len(this_month_txs),
        "category_breakdown": category_breakdown,
        "trend": trend,
        "budget_alerts": budget_alerts,
        "over_budget_count": over_budget_count,
        "warn_budget_count": warn_budget_count,
        "recurring_upcoming": recurring_upcoming[:5],
    }


def find_due_recurring(book: dict[str, Any], today: date | None = None) -> list[dict[str, Any]]:
    """Find recurring rules whose day_of_month has been reached this month and not yet run."""
    if today is None:
        today = date.today()
    due = []
    for rule in book.get("recurring", []):
        if not rule.get("active", True):
            continue
        day = min(rule["day_of_month"], 28)
        # If we're past the day this month, and last_run is not this month, it's due
        if today.day < day:
            continue
        last_run = rule.get("last_run_date")
        if last_run:
            try:
                lr = _parse_date(last_run)
                if lr.year == today.year and lr.month == today.month:
                    continue
            except ValueError:
                pass
        due.append(rule)
    return due
