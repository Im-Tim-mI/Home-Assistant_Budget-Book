# Budget Book Add-on Documentation

## Opening the App

After installing and starting the add-on, open Budget Book from the Home Assistant sidebar or from the add-on page. The UI is the same panel as the Budget Book custom integration v1.2.0.

## Data Storage

Budget data is stored at:

```text
/data/budget_book.json
```

This file is inside the add-on persistent data volume and is included in Home Assistant backups.

Data saved by add-on 0.1.0 is converted automatically on first start; the original file is kept as `/data/budget_book.json.pre-migration`.

### Moving data from the custom integration

1. In the integration panel, open Settings and use Export JSON.
2. In the add-on panel, open Settings and use Import JSON with that file.

## Sensors

The add-on publishes these entities through the Home Assistant API:

| Entity | Meaning |
| --- | --- |
| `sensor.budget_book_month_expense` | This month's expense (attributes: category breakdown, budget alerts) |
| `sensor.budget_book_month_income` | This month's income |
| `sensor.budget_book_month_balance` | This month's balance |
| `sensor.budget_book_balance` | Total balance |
| `sensor.budget_book_transaction_count` | Transaction count |
| `sensor.budget_book_over_budget_count` | Over-budget category count (attribute: `alerts`) |
| `sensor.budget_book_active_book` | Active book name |
| `sensor.budget_book_all_books` | Number of books |

They are updated after each change and republished every 5 minutes (Home Assistant forgets API-created states when it restarts). They have no unique ID, so they cannot be renamed in the UI.

## Recurring Entries

Due recurring entries are inserted when the add-on starts and every day at 09:00 (add-on container time). Use "Run now" on the Recurring tab to trigger it manually.

## Options

| Option | Description |
| --- | --- |
| `log_level` | Controls add-on logging verbosity. |

## Recovery

If `/data/budget_book.json` cannot be read, the add-on refuses to start rather than overwriting it. Check the add-on log, then fix or restore the file from a backup.

## Differences from the Integration

- `budget_book.*` Home Assistant services are not available; use the panel.
- Do not run the custom integration and this add-on at the same time: both write `sensor.budget_book_*`.
- Shared UI, language, analytics, data shape, import/export, sample data and migration code are maintained from the repository `shared/core/` directory.
