"""Budget Book integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_change

from .analytics import find_due_recurring
from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_RECURRING,
    SERVICE_ADD_TRANSACTION,
    SERVICE_ADD_CATEGORY,
    SERVICE_CLEAR_ALL,
    SERVICE_CREATE_BOOK,
    SERVICE_DELETE_BOOK,
    SERVICE_DELETE_CATEGORY,
    SERVICE_DELETE_RECURRING,
    SERVICE_DELETE_TRANSACTION,
    SERVICE_LOAD_SAMPLE,
    SERVICE_RENAME_BOOK,
    SERVICE_REPLACE_DATA,
    SERVICE_RUN_RECURRING,
    SERVICE_SET_BUDGET,
    SIGNAL_UPDATE,
    TYPE_EXPENSE,
    TYPE_INCOME,
)
from .store import BudgetStore

_LOGGER = logging.getLogger(__name__)

PANEL_URL = "/budget_book_static"
PANEL_TITLE = "記帳本"
PANEL_ICON = "mdi:notebook"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Budget Book from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    store = BudgetStore(hass)
    await store.async_load()

    hass.data[DOMAIN][entry.entry_id] = {"store": store}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services once
    if not hass.services.has_service(DOMAIN, SERVICE_ADD_TRANSACTION):
        await _async_register_services(hass)

    # Register panel once
    if DOMAIN + "_panel_registered" not in hass.data:
        await _async_register_panel(hass)
        hass.data[DOMAIN + "_panel_registered"] = True

    # Daily check at 09:00 for due recurring entries
    if DOMAIN + "_daily_listener" not in hass.data:
        async def _daily_check(_now=None):
            await _run_recurring_for_all_books(hass)

        hass.data[DOMAIN + "_daily_listener"] = async_track_time_change(
            hass, _daily_check, hour=9, minute=0, second=0
        )
        # Also run once now (10s delayed so other things load first)
        from homeassistant.helpers.event import async_call_later
        async_call_later(hass, 10, _daily_check)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_register_panel(hass: HomeAssistant) -> None:
    www_dir = Path(__file__).parent / "www"
    # Version derived from file mtimes so the Companion app WebView drops stale caches
    version = await hass.async_add_executor_job(
        lambda: int(max(f.stat().st_mtime for f in www_dir.iterdir() if f.is_file()))
    )
    await hass.http.async_register_static_paths(
        [StaticPathConfig(PANEL_URL, str(www_dir), cache_headers=False)]
    )
    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        frontend_url_path="budget_book",
        config={"url": f"{PANEL_URL}/index.html?v={version}"},
        require_admin=False,
    )
    _LOGGER.info("Registered Budget Book panel")


def _get_store(hass: HomeAssistant) -> BudgetStore | None:
    entries = hass.data.get(DOMAIN, {})
    for v in entries.values():
        if isinstance(v, dict) and "store" in v:
            return v["store"]
    return None


async def _run_recurring_for_all_books(hass: HomeAssistant) -> None:
    """Daily task: scan all books and inject due recurring transactions."""
    store = _get_store(hass)
    if not store:
        return
    today = date.today()
    today_str = today.isoformat()
    added_count = 0
    for book_id, book in list(store.books.items()):
        due_rules = find_due_recurring(book, today)
        for rule in due_rules:
            await store.async_add_transaction(book_id, {
                "date": today_str,
                "type": rule["type"],
                "amount": rule["amount"],
                "category": rule["category"],
                "note": f"[固定] {rule['name']}",
                "recurring_id": rule["id"],
            })
            await store.async_update_recurring(book_id, rule["id"], {"last_run_date": today_str})
            added_count += 1
    if added_count > 0:
        _LOGGER.info("Auto-inserted %d recurring transactions", added_count)
        async_dispatcher_send(hass, SIGNAL_UPDATE)


# ---- Service Schemas ----

ADD_TX_SCHEMA = vol.Schema({
    vol.Optional("book_id"): cv.string,
    vol.Required("date"): cv.string,
    vol.Optional("time"): vol.Match(r"^([01]\d|2[0-3]):[0-5]\d$"),
    vol.Required("type"): vol.In([TYPE_INCOME, TYPE_EXPENSE]),
    vol.Required("amount"): vol.Coerce(float),
    vol.Optional("category", default="other"): cv.string,
    vol.Optional("note", default=""): cv.string,
})

DEL_TX_SCHEMA = vol.Schema({
    vol.Optional("book_id"): cv.string,
    vol.Required("transaction_id"): cv.string,
})

CREATE_BOOK_SCHEMA = vol.Schema({
    vol.Required("name"): cv.string,
    vol.Optional("currency", default="TWD"): cv.string,
})

DELETE_BOOK_SCHEMA = vol.Schema({
    vol.Required("book_id"): cv.string,
})

RENAME_BOOK_SCHEMA = vol.Schema({
    vol.Required("book_id"): cv.string,
    vol.Required("name"): cv.string,
})

SET_BUDGET_SCHEMA = vol.Schema({
    vol.Optional("book_id"): cv.string,
    vol.Required("category"): cv.string,
    vol.Optional("amount"): vol.Any(None, vol.Coerce(float)),
})

ADD_CATEGORY_SCHEMA = vol.Schema({
    vol.Optional("book_id"): cv.string,
    vol.Required("name"): cv.string,
    vol.Required("type"): vol.In([TYPE_INCOME, TYPE_EXPENSE]),
    vol.Optional("icon"): cv.string,
    vol.Optional("color"): cv.string,
})

DELETE_CATEGORY_SCHEMA = vol.Schema({
    vol.Optional("book_id"): cv.string,
    vol.Required("category"): cv.string,
})

ADD_RECURRING_SCHEMA = vol.Schema({
    vol.Optional("book_id"): cv.string,
    vol.Required("name"): cv.string,
    vol.Optional("type", default="expense"): vol.In([TYPE_INCOME, TYPE_EXPENSE]),
    vol.Required("amount"): vol.Coerce(float),
    vol.Optional("category", default="other"): cv.string,
    vol.Required("day_of_month"): vol.All(vol.Coerce(int), vol.Range(min=1, max=31)),
    vol.Optional("note", default=""): cv.string,
})

DEL_RECURRING_SCHEMA = vol.Schema({
    vol.Optional("book_id"): cv.string,
    vol.Required("recurring_id"): cv.string,
})

REPLACE_DATA_SCHEMA = vol.Schema({
    vol.Required("data"): dict,
})

SET_ACTIVE_BOOK_SCHEMA = vol.Schema({
    vol.Required("book_id"): cv.string,
})


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register all services."""

    def _active_book_id(call_data: dict[str, Any]) -> str | None:
        store = _get_store(hass)
        if not store:
            return None
        return call_data.get("book_id") or store.data.get("active_book_id")

    async def handle_add_tx(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        book_id = _active_book_id(dict(call.data))
        if not book_id:
            return
        d = dict(call.data)
        d.pop("book_id", None)
        await store.async_add_transaction(book_id, d)
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_del_tx(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        book_id = _active_book_id(dict(call.data))
        if not book_id:
            return
        await store.async_delete_transaction(book_id, call.data["transaction_id"])
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_create_book(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        await store.async_create_book(
            name=call.data["name"], currency=call.data.get("currency", "TWD")
        )
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_delete_book(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        try:
            await store.async_delete_book(call.data["book_id"])
            async_dispatcher_send(hass, SIGNAL_UPDATE)
        except ValueError as e:
            _LOGGER.warning("Delete book: %s", e)

    async def handle_rename_book(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        await store.async_rename_book(call.data["book_id"], call.data["name"])
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_set_active_book(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        await store.async_set_active_book(call.data["book_id"])
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_set_budget(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        book_id = _active_book_id(dict(call.data))
        if not book_id:
            return
        await store.async_set_budget(
            book_id, call.data["category"], call.data.get("amount")
        )
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_add_category(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        book_id = _active_book_id(dict(call.data))
        if not book_id:
            return
        try:
            await store.async_add_category(
                book_id,
                name=call.data["name"],
                cat_type=call.data["type"],
                icon=call.data.get("icon"),
                color=call.data.get("color"),
            )
            async_dispatcher_send(hass, SIGNAL_UPDATE)
        except ValueError as e:
            _LOGGER.warning("Add category: %s", e)
            raise

    async def handle_delete_category(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        book_id = _active_book_id(dict(call.data))
        if not book_id:
            return
        try:
            await store.async_delete_category(book_id, call.data["category"])
            async_dispatcher_send(hass, SIGNAL_UPDATE)
        except ValueError as e:
            _LOGGER.warning("Delete category: %s", e)
            raise

    async def handle_add_recurring(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        book_id = _active_book_id(dict(call.data))
        if not book_id:
            return
        d = dict(call.data)
        d.pop("book_id", None)
        await store.async_add_recurring(book_id, d)
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_del_recurring(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        book_id = _active_book_id(dict(call.data))
        if not book_id:
            return
        await store.async_delete_recurring(book_id, call.data["recurring_id"])
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_run_recurring(call: ServiceCall) -> None:
        await _run_recurring_for_all_books(hass)

    async def handle_load_sample(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        from .sample_data import build_sample
        data = build_sample()
        await store.async_replace_data(data)
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_clear_all(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        await store.async_clear_active_book_data()
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    async def handle_replace_data(call: ServiceCall) -> None:
        store = _get_store(hass)
        if not store:
            return
        await store.async_replace_data(call.data["data"])
        async_dispatcher_send(hass, SIGNAL_UPDATE)

    hass.services.async_register(DOMAIN, SERVICE_ADD_TRANSACTION, handle_add_tx, schema=ADD_TX_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_TRANSACTION, handle_del_tx, schema=DEL_TX_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CREATE_BOOK, handle_create_book, schema=CREATE_BOOK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_BOOK, handle_delete_book, schema=DELETE_BOOK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RENAME_BOOK, handle_rename_book, schema=RENAME_BOOK_SCHEMA)
    hass.services.async_register(DOMAIN, "set_active_book", handle_set_active_book, schema=SET_ACTIVE_BOOK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_BUDGET, handle_set_budget, schema=SET_BUDGET_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_CATEGORY, handle_add_category, schema=ADD_CATEGORY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_CATEGORY, handle_delete_category, schema=DELETE_CATEGORY_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_RECURRING, handle_add_recurring, schema=ADD_RECURRING_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_RECURRING, handle_del_recurring, schema=DEL_RECURRING_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_RUN_RECURRING, handle_run_recurring)
    hass.services.async_register(DOMAIN, SERVICE_LOAD_SAMPLE, handle_load_sample)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_ALL, handle_clear_all)
    hass.services.async_register(DOMAIN, SERVICE_REPLACE_DATA, handle_replace_data, schema=REPLACE_DATA_SCHEMA)
