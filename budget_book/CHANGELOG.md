# Changelog

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
