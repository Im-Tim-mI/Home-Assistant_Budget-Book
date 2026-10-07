"""Budget Book data store.

Schema:
{
  "books": {
    "<book_id>": {
      "id": str,
      "name": str,
      "currency": str,
      "created_at": str (iso),
      "transactions": [
        {
          "id": str,
          "date": "YYYY-MM-DD",
          "time": "HH:MM" | null  # 24h, optional
          "type": "income" | "expense",
          "amount": float,
          "category": str (category id),
          "note": str,
          "recurring_id": str | null  # if generated from a recurring rule
        }, ...
      ],
      "categories": [
        {"id": str, "name": str, "icon": str, "color": str, "type": "income"|"expense"}, ...
      ],
      "budgets": {
        "<category_id>": float  # monthly limit
      },
      "recurring": [
        {
          "id": str,
          "name": str,
          "type": "income"|"expense",
          "amount": float,
          "category": str,
          "day_of_month": int (1-31),
          "note": str,
          "last_run_date": "YYYY-MM-DD" | null,
          "active": bool
        }, ...
      ]
    }
  },
  "active_book_id": str | null
}
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_EXPENSE_CATEGORIES,
    DEFAULT_INCOME_CATEGORIES,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def _make_default_categories() -> list[dict[str, Any]]:
    cats = []
    for c in DEFAULT_INCOME_CATEGORIES:
        cats.append({**c, "type": "income"})
    for c in DEFAULT_EXPENSE_CATEGORIES:
        cats.append({**c, "type": "expense"})
    return cats


def make_default_book(name: str = "我的記帳本", currency: str = "TWD") -> dict[str, Any]:
    return {
        "id": _gen_id(),
        "name": name,
        "currency": currency,
        "created_at": _now_iso(),
        "transactions": [],
        "categories": _make_default_categories(),
        "budgets": {},
        "recurring": [],
    }


class BudgetStore:
    """Persistent storage for budget book data."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"books": {}, "active_book_id": None}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data and isinstance(data, dict) and "books" in data:
            self._data = data
        else:
            self._data = {"books": {}, "active_book_id": None}

        # Ensure at least one book exists
        if not self._data["books"]:
            book = make_default_book()
            self._data["books"][book["id"]] = book
            self._data["active_book_id"] = book["id"]
            await self.async_save()

        # Ensure active_book_id is valid
        if (
            self._data["active_book_id"] is None
            or self._data["active_book_id"] not in self._data["books"]
        ):
            self._data["active_book_id"] = next(iter(self._data["books"]))
            await self.async_save()

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @property
    def books(self) -> dict[str, Any]:
        return self._data["books"]

    @property
    def active_book(self) -> dict[str, Any] | None:
        bid = self._data["active_book_id"]
        return self._data["books"].get(bid) if bid else None

    def get_book(self, book_id: str) -> dict[str, Any] | None:
        return self._data["books"].get(book_id)

    # ---- Book management ----

    async def async_create_book(self, name: str, currency: str = "TWD") -> str:
        book = make_default_book(name=name, currency=currency)
        self._data["books"][book["id"]] = book
        if not self._data["active_book_id"]:
            self._data["active_book_id"] = book["id"]
        await self.async_save()
        return book["id"]

    async def async_delete_book(self, book_id: str) -> None:
        if book_id not in self._data["books"]:
            return
        if len(self._data["books"]) <= 1:
            raise ValueError("Cannot delete the last book")
        del self._data["books"][book_id]
        if self._data["active_book_id"] == book_id:
            self._data["active_book_id"] = next(iter(self._data["books"]))
        await self.async_save()

    async def async_rename_book(self, book_id: str, new_name: str) -> None:
        book = self._data["books"].get(book_id)
        if book:
            book["name"] = new_name
            await self.async_save()

    async def async_set_active_book(self, book_id: str) -> None:
        if book_id in self._data["books"]:
            self._data["active_book_id"] = book_id
            await self.async_save()

    # ---- Transactions ----

    async def async_add_transaction(self, book_id: str, tx: dict[str, Any]) -> str:
        book = self._data["books"].get(book_id)
        if not book:
            raise ValueError(f"Book {book_id} not found")

        # Normalize
        try:
            datetime.strptime(tx["date"], "%Y-%m-%d")
        except (ValueError, KeyError):
            try:
                d = datetime.strptime(tx["date"], "%Y/%m/%d")
                tx["date"] = d.strftime("%Y-%m-%d")
            except (ValueError, KeyError):
                raise ValueError(f"invalid date: {tx.get('date')}")

        tid = tx.get("id") or _gen_id()
        entry = {
            "id": tid,
            "date": tx["date"],
            "time": tx.get("time") or None,
            "type": tx["type"],
            "amount": float(tx["amount"]),
            "category": tx.get("category") or "other",
            "note": tx.get("note") or "",
            "recurring_id": tx.get("recurring_id"),
        }
        book["transactions"].append(entry)
        await self.async_save()
        return tid

    async def async_delete_transaction(self, book_id: str, tx_id: str) -> None:
        book = self._data["books"].get(book_id)
        if not book:
            return
        book["transactions"] = [t for t in book["transactions"] if t["id"] != tx_id]
        await self.async_save()

    # ---- Budgets ----

    async def async_set_budget(
        self, book_id: str, category_id: str, amount: float | None
    ) -> None:
        book = self._data["books"].get(book_id)
        if not book:
            return
        if amount is None or amount <= 0:
            book["budgets"].pop(category_id, None)
        else:
            book["budgets"][category_id] = float(amount)
        await self.async_save()

    # ---- Categories ----

    @staticmethod
    def _slugify(name: str) -> str:
        """Build a simple ascii-ish slug; fall back to a random id."""
        import re

        slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
        return slug or _gen_id()

    async def async_add_category(
        self,
        book_id: str,
        name: str,
        cat_type: str,
        icon: str | None = None,
        color: str | None = None,
    ) -> str:
        """Add a category to a specific book.

        Categories are stored per-book, so the same name can exist in
        different books independently.
        """
        book = self._data["books"].get(book_id)
        if not book:
            raise ValueError(f"Book {book_id} not found")

        name = (name or "").strip()
        if not name:
            raise ValueError("Category name is required")
        if cat_type not in ("income", "expense"):
            raise ValueError(f"invalid category type: {cat_type}")

        categories = book.setdefault("categories", [])

        # Reject duplicate name within the same type for this book
        for c in categories:
            if c.get("type") == cat_type and c.get("name") == name:
                raise ValueError(f"Category '{name}' already exists")

        # Generate a unique id within this book
        base = self._slugify(name)
        existing_ids = {c["id"] for c in categories}
        cat_id = base
        while cat_id in existing_ids:
            cat_id = f"{base}_{_gen_id()[:4]}"

        entry = {
            "id": cat_id,
            "name": name,
            "icon": icon or ("mdi:cash-plus" if cat_type == "income" else "mdi:tag"),
            "color": color or "#95A5A6",
            "type": cat_type,
        }
        categories.append(entry)
        await self.async_save()
        return cat_id

    async def async_delete_category(self, book_id: str, category_id: str) -> None:
        """Delete a category from a book.

        Also removes the matching budget entry (budget column stays in sync).
        Existing transactions that referenced this category are reassigned to
        the fallback "other" / "income_other" category so historical data is
        not lost. Refuses to delete if it is the last category of its type.
        """
        book = self._data["books"].get(book_id)
        if not book:
            return

        categories = book.get("categories", [])
        target = next((c for c in categories if c["id"] == category_id), None)
        if target is None:
            return

        cat_type = target.get("type", "expense")
        same_type = [c for c in categories if c.get("type") == cat_type]
        if len(same_type) <= 1:
            raise ValueError("Cannot delete the last category of its type")

        # Determine a fallback category for orphaned transactions
        fallback_id = "income_other" if cat_type == "income" else "other"
        if not any(c["id"] == fallback_id for c in categories):
            # Use the first remaining category of the same type
            fallback_id = next(
                c["id"] for c in same_type if c["id"] != category_id
            )

        # Remove the category
        book["categories"] = [c for c in categories if c["id"] != category_id]

        # Sync budgets: drop the budget entry for this category
        if "budgets" in book:
            book["budgets"].pop(category_id, None)

        # Reassign transactions referencing the deleted category
        for t in book.get("transactions", []):
            if t.get("category") == category_id:
                t["category"] = fallback_id

        # Reassign recurring rules referencing the deleted category
        for r in book.get("recurring", []):
            if r.get("category") == category_id:
                r["category"] = fallback_id

        await self.async_save()

    # ---- Recurring ----

    async def async_add_recurring(self, book_id: str, rule: dict[str, Any]) -> str:
        book = self._data["books"].get(book_id)
        if not book:
            raise ValueError(f"Book {book_id} not found")
        rid = rule.get("id") or _gen_id()
        entry = {
            "id": rid,
            "name": rule["name"],
            "type": rule.get("type", "expense"),
            "amount": float(rule["amount"]),
            "category": rule.get("category") or "other",
            "day_of_month": int(rule.get("day_of_month", 1)),
            "note": rule.get("note", ""),
            "last_run_date": rule.get("last_run_date"),
            "active": rule.get("active", True),
        }
        book["recurring"].append(entry)
        await self.async_save()
        return rid

    async def async_delete_recurring(self, book_id: str, rule_id: str) -> None:
        book = self._data["books"].get(book_id)
        if not book:
            return
        book["recurring"] = [r for r in book["recurring"] if r["id"] != rule_id]
        await self.async_save()

    async def async_update_recurring(
        self, book_id: str, rule_id: str, updates: dict[str, Any]
    ) -> None:
        book = self._data["books"].get(book_id)
        if not book:
            return
        for r in book["recurring"]:
            if r["id"] == rule_id:
                r.update(updates)
                break
        await self.async_save()

    # ---- Bulk ----

    async def async_clear_active_book_data(self) -> None:
        book = self.active_book
        if book:
            book["transactions"] = []
            book["budgets"] = {}
            book["recurring"] = []
            await self.async_save()

    async def async_replace_data(self, data: dict[str, Any]) -> None:
        """Replace entire data (for import)."""
        if "books" not in data:
            raise ValueError("Invalid data: missing 'books'")
        self._data = data
        if (
            self._data.get("active_book_id") not in self._data["books"]
            and self._data["books"]
        ):
            self._data["active_book_id"] = next(iter(self._data["books"]))
        await self.async_save()
