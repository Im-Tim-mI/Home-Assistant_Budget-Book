# Changelog

## 1.2.5b2 (beta)

- "Never show this ad" is now a checkbox with a larger, highlighted label. Checking it saves the choice immediately; unchecking it clears the choice.

## 1.2.5b1 (beta)

- Add a Logitech Taiwan store discount ad: shown on startup with a bottom-left "Never show this ad" option, plus a dedicated Logitech tab.
- Add the same ad to the README in English, Traditional Chinese and Simplified Chinese.

## 1.2.4

- Recurring rules set to day 29, 30 or 31 now run on the last day of shorter months (Feb 28/29, Apr 30, ...) instead of always on the 28th.
- Home panel "upcoming" list shows the "today" badge for rules due today instead of moving them to next month.
- Upcoming due dates are shown in local time (previously one day early in UTC+ timezones).
- Add analytics tests covering the shared core, HACS integration and add-on copies.

## 1.2.3

- Add root-level HACS brand assets (`brand/icon.png`, `brand/icon@2x.png`, `brand/icon.svg`) so the HACS repository list can show the Budget Book icon.

## 1.2.2

- Allow the HACS integration and Supervisor Add-on to be installed together with shared data.
- Use the HACS integration's HA storage as the shared source of truth when both install targets are present.
- Automatically migrate existing add-on `/data/budget_book.json` data into the integration when the integration is empty.
- Preserve timestamped local add-on backups before adopting integration data, and keep old-format migration backups.
- Avoid overwriting integration-owned `sensor.budget_book_*` states when the integration is installed.

## 1.2.1

- Sync the Supervisor Add-on version with the HACS integration version.
- Align the add-on sidebar icon/title with the integration sidebar entry.
- Sync the Home Assistant sidebar entry title with Budget Book's Auto/English/繁中/简中 language mode while the panel is open.

## 0.3.0

- Move the add-on into the main `Home-Assistant_Budget-Book` repository so the same repo supports HACS integration and Supervisor Add-on installation.
- Add `shared/core/` plus `scripts/sync_shared_core.py` so shared UI, translations, analytics, sample data, data shape and migration logic are synced into both adapters.
- Keep the add-on ingress API and `/data/budget_book.json` persistence from 0.2.0.

## 0.2.0

- Port the original Budget Book integration (v1.1.4) instead of a rewrite: same panel UI, styles, translations, store, analytics and sample data.
- Restore all original features: multiple books, transaction edit/delete with time, categories, budgets and alerts, charts, recurring entries (daily 09:00 auto-insert), JSON import/export, sample data, Auto/English/繁中/简中 languages.
- Publish the original `sensor.budget_book_*` entities to Home Assistant for automations.
- Bundle Chart.js locally so the panel works offline.
- Migrate data saved by 0.1.0 automatically (backup kept as `budget_book.json.pre-migration`).

## 0.1.0

- Initial Supervisor Add-on release.
- Add public-ready add-on repository structure.
- Add `repository.yaml` and `budget_book/config.yaml`.
- Add standalone Python backend with persistent `/data/budget_book.json` storage.
- Add ingress web UI for basic transaction tracking.
- Add Add-on Store icon and logo assets.
- Add English, Traditional Chinese, and Simplified Chinese repository documentation.
