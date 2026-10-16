#!/usr/bin/env python3
"""Sync shared Budget Book core into the HACS integration and add-on adapters."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared/core"
INTEGRATION = ROOT / "custom_components/budget_book"
ADDON_APP = ROOT / "budget_book/rootfs/app"

INTEGRATION_FILES = [
    "analytics.py",
    "const.py",
    "sample_data.py",
    "store.py",
    "www/app.js",
    "www/index.html",
    "www/style.css",
    "www/locales/en.json",
    "www/locales/zh-Hant.json",
    "www/locales/zh-Hans.json",
]

ADDON_SHARED_FILES = [
    "analytics.py",
    "const.py",
    "www/style.css",
]

ADDON_LOCALES = ["en.json", "zh-Hant.json", "zh-Hans.json"]

BINARY_FILES = [
    "www/ad-logitech-logitim.png",
]


ADDON_CONNECTION = """// Connection
// ============================================================

// Keep the original panel's state shape; transport stays inside ingress.
async function readAddon(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || response.statusText);
  return result;
}

function refreshParentLanguage() {
  try {
    parentHass = window.parent.document.querySelector('home-assistant')?.hass || null;
  } catch (_) { parentHass = null; }
}

async function callService(domain, service, data = {}) {
  states = await readAddon(`api/services/${domain}/${service}`, {
    method: 'POST', body: JSON.stringify(data),
  });
  render();
}

function getDataSnapshot(sourceStates = states) {
  return sourceStates?.['sensor.budget_book_all_books']?.attributes?.full_data || null;
}

async function refreshStateFromHomeAssistant({ forceRender = false } = {}) {
  if (refreshInFlight) return false;
  refreshInFlight = true;
  try {
    const next = await readAddon('api/states');
    const changed = JSON.stringify(next) !== JSON.stringify(states);
    states = next;
    refreshParentLanguage();
    refreshLanguageFromChoice();
    // Metrics can change at midnight even without new transactions.
    if (forceRender || changed) render();
    return forceRender || changed;
  } finally {
    refreshInFlight = false;
  }
}

function showError(msg) {
  $('loading').style.display = 'none';
  $('main').style.display = 'none';
  $('error').style.display = 'block';
  $('error-msg').textContent = msg;
}

async function connectHA() {
  try {
    await refreshStateFromHomeAssistant({ forceRender: true });
    setInterval(() => {
      refreshStateFromHomeAssistant().catch(err => log('poll failed:', err.message));
    }, 3000);
    return true;
  } catch (error) {
    showError(t('error.connect_failed', { message: error.message }));
    return false;
  }
}

"""


def copy_text(src: Path, dst: Path, transform=None) -> None:
    text = src.read_text()
    if transform:
        text = transform(text)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text)


def copy_binary(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())


def addon_sample_data(text: str) -> str:
    return text.replace("from .const import", "from const import")


def addon_store(text: str) -> str:
    text = text.replace("from homeassistant.core import HomeAssistant\n", "")
    text = text.replace("from homeassistant.helpers.storage import Store\n", "from persistence import Store\n")
    text = text.replace("from .const import", "from const import")
    text = text.replace(
        "    def __init__(self, hass: HomeAssistant) -> None:\n"
        "        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)\n",
        "    def __init__(self, path: str) -> None:\n"
        "        self._store = Store(path)\n",
    )
    text = text.replace(
        "        self._backup_store: Store | None = Store(\n"
        "            hass, STORAGE_VERSION, f\"{STORAGE_KEY}_pre_migration\"\n"
        "        )\n",
        "        self._backup_store = None\n",
    )
    return text


def addon_index(text: str) -> str:
    text = text.replace(
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>',
        '<script src="vendor/chart.umd.js"></script>',
    )
    return text.replace(
        "記帳本 v1.2.5b2 — 整合於 Home Assistant，資料存在 HA storage 並隨著系統備份。",
        "記帳本 Add-on v1.2.5b2 · 移植自記帳本 v1.2.5b2，資料儲存在 /data/budget_book.json。",
    )


def addon_locale(text: str) -> str:
    return text.replace(
        "記帳本 v1.2.5b2 — 整合於 Home Assistant，資料存在 HA storage 並隨著系統備份。",
        "記帳本 Add-on v1.2.5b2 · 移植自記帳本 v1.2.5b2，資料儲存在 /data/budget_book.json。",
    ).replace(
        "Budget Book v1.2.5b2 — integrated with Home Assistant. Data is stored in HA storage and included in system backups.",
        "Budget Book Add-on v1.2.5b2 · Ported from Budget Book v1.2.5b2, stored in /data/budget_book.json.",
    ).replace(
        "记账本 v1.2.5b2 — 集成于 Home Assistant，数据储存在 HA storage，并随系统备份保存。",
        "记账本 Add-on v1.2.5b2 · 移植自记账本 v1.2.5b2，数据存放在 /data/budget_book.json。",
    )


def addon_app_js(text: str) -> str:
    start = text.index("// Connection\n// ============================================================\n")
    end = text.index("// ============================================================\n// Data accessors", start)
    return text[:start] + ADDON_CONNECTION + text[end:]


def main() -> None:
    for rel in INTEGRATION_FILES:
        copy_text(SHARED / rel, INTEGRATION / rel)

    for rel in ADDON_SHARED_FILES:
        copy_text(SHARED / rel, ADDON_APP / rel)

    copy_text(SHARED / "sample_data.py", ADDON_APP / "sample_data.py", addon_sample_data)
    copy_text(SHARED / "store.py", ADDON_APP / "store.py", addon_store)
    copy_text(SHARED / "www/index.html", ADDON_APP / "www/index.html", addon_index)
    copy_text(SHARED / "www/app.js", ADDON_APP / "www/app.js", addon_app_js)

    for name in ADDON_LOCALES:
        copy_text(SHARED / "www/locales" / name, ADDON_APP / "www/locales" / name, addon_locale)

    for rel in BINARY_FILES:
        copy_binary(SHARED / rel, INTEGRATION / rel)
        copy_binary(SHARED / rel, ADDON_APP / rel)


if __name__ == "__main__":
    main()
