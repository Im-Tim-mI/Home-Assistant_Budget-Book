"""Sensor platform for Budget Book.

Exposes summary sensors for the currently active book so HA automations
can react (e.g., budget exceeded notifications).
"""
from __future__ import annotations

import copy
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .analytics import compute_book_metrics
from .const import DOMAIN, SIGNAL_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    store = entry_data["store"]
    coord = BudgetCoordinator(hass, store)

    sensors = [
        BudgetSensor(coord, entry.entry_id, "month_expense", "本月支出", "TWD", "mdi:cash-minus", SensorStateClass.MEASUREMENT),
        BudgetSensor(coord, entry.entry_id, "month_income", "本月收入", "TWD", "mdi:cash-plus", SensorStateClass.MEASUREMENT),
        BudgetSensor(coord, entry.entry_id, "month_balance", "本月結餘", "TWD", "mdi:scale-balance", SensorStateClass.MEASUREMENT),
        BudgetSensor(coord, entry.entry_id, "balance", "總結餘", "TWD", "mdi:wallet", SensorStateClass.MEASUREMENT),
        BudgetSensor(coord, entry.entry_id, "transaction_count", "總交易筆數", "筆", "mdi:counter", SensorStateClass.TOTAL_INCREASING),
        BudgetSensor(coord, entry.entry_id, "over_budget_count", "預算超支類別數", "個", "mdi:alert", SensorStateClass.MEASUREMENT),
    ]
    sensors.append(BudgetActiveBookSensor(coord, entry.entry_id))
    sensors.append(BudgetBooksSensor(coord, entry.entry_id))

    async_add_entities(sensors)


class BudgetCoordinator:
    def __init__(self, hass: HomeAssistant, store) -> None:
        self.hass = hass
        self.store = store
        self.metrics: dict[str, Any] = {}
        self._listeners: list = []
        self._unsub = None

    async def async_init(self) -> None:
        self.refresh()
        self._unsub = async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE, self._on_update
        )

    @callback
    def _on_update(self) -> None:
        self.refresh()
        for cb in list(self._listeners):
            cb()

    def refresh(self) -> None:
        book = self.store.active_book
        if book:
            self.metrics = compute_book_metrics(book)
        else:
            self.metrics = {}

    def register(self, cb):
        self._listeners.append(cb)
        def _unsub():
            if cb in self._listeners:
                self._listeners.remove(cb)
        return _unsub


class BudgetSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(self, coord, entry_id, key, name_zh, unit, icon, state_class):
        self._coord = coord
        self._key = key
        self._attr_name = name_zh
        self.entity_id = f"sensor.budget_book_{key}"
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        if state_class:
            self._attr_state_class = state_class

    async def async_added_to_hass(self) -> None:
        if not self._coord.metrics:
            await self._coord.async_init()
        self.async_on_remove(self._coord.register(self.async_write_ha_state))

    @property
    def native_value(self) -> Any:
        return self._coord.metrics.get(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Attach helpful context on the headline sensor
        if self._key == "month_expense":
            return {
                "month_label": self._coord.metrics.get("month_label"),
                "this_month_count": self._coord.metrics.get("this_month_count"),
                "category_breakdown": self._coord.metrics.get("category_breakdown", []),
                "budget_alerts": self._coord.metrics.get("budget_alerts", []),
            }
        if self._key == "over_budget_count":
            return {
                "alerts": self._coord.metrics.get("budget_alerts", []),
            }
        return {}


class BudgetActiveBookSensor(SensorEntity):
    _attr_should_poll = False
    _attr_name = "目前記帳本"
    _attr_icon = "mdi:notebook"

    def __init__(self, coord, entry_id):
        self._coord = coord
        self.entity_id = "sensor.budget_book_active_book"
        self._attr_unique_id = f"{entry_id}_active_book"

    async def async_added_to_hass(self) -> None:
        if not self._coord.metrics:
            await self._coord.async_init()
        self.async_on_remove(self._coord.register(self.async_write_ha_state))

    @property
    def native_value(self) -> Any:
        book = self._coord.store.active_book
        return book["name"] if book else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        book = self._coord.store.active_book
        if not book:
            return {}
        return {
            "book_id": book["id"],
            "currency": book.get("currency", "TWD"),
            "transaction_count": len(book.get("transactions", [])),
            "category_count": len(book.get("categories", [])),
            "recurring_count": len(book.get("recurring", [])),
            "budget_count": len(book.get("budgets", {})),
        }


class BudgetBooksSensor(SensorEntity):
    """Diagnostic sensor exposing all books."""

    _attr_should_poll = False
    _attr_name = "所有記帳本"
    _attr_icon = "mdi:book-multiple"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coord, entry_id):
        self._coord = coord
        self.entity_id = "sensor.budget_book_all_books"
        self._attr_unique_id = f"{entry_id}_all_books"

    async def async_added_to_hass(self) -> None:
        if not self._coord.metrics:
            await self._coord.async_init()
        self.async_on_remove(self._coord.register(self.async_write_ha_state))

    @property
    def native_value(self) -> Any:
        return len(self._coord.store.books)

    @property
    def native_unit_of_measurement(self) -> str:
        return "本"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Expose full data for the panel to consume
        return {
            "books": [
                {
                    "id": b["id"],
                    "name": b["name"],
                    "currency": b.get("currency", "TWD"),
                    "transaction_count": len(b.get("transactions", [])),
                }
                for b in self._coord.store.books.values()
            ],
            "active_book_id": self._coord.store.data.get("active_book_id"),
            # Deep copy: the store mutates its dict in place, so passing the same
            # object makes old/new state attributes compare equal and the
            # frontend never receives the updated data.
            "full_data": copy.deepcopy(self._coord.store.data),
        }
