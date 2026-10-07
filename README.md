# Home-Assistant 記帳本 (Budget Book)

[繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

A Home Assistant custom integration that adds a sidebar budgeting panel with transaction tracking, income and expense summaries, category budgets, recurring expenses, and JSON import/export. Data is stored in Home Assistant storage, so it is included with your regular HA backups.

Current release: `v1.1.1`

## Screenshots

### Desktop

| Overview | English UI |
| --- | --- |
| ![Overview screen](docs/images/screenshot-overview.png) | ![English overview screen](docs/images/screenshot-overview-en.png) |

| Transactions | Language settings |
| --- | --- |
| ![Transactions screen](docs/images/screenshot-transactions.png) | ![Language settings screen](docs/images/screenshot-settings-language.png) |

| Charts | Budgets |
| --- | --- |
| ![Charts screen](docs/images/screenshot-charts.png) | ![Budgets screen](docs/images/screenshot-budgets.png) |

### Mobile

![Mobile overview screen](docs/images/screenshot-mobile-overview-en.png)

## Features

- Manage multiple budget books for household, personal, or project expenses.
- Record income and expenses with categories, notes, dates, and times.
- Track monthly expenses, monthly income, monthly balance, and total balance.
- View category spending, six-month trends, and budget usage charts.
- Set monthly category budgets with 80% warning and over-budget alerts.
- Configure recurring monthly entries that are checked automatically every day at 09:00.
- Import, export, and load sample data as JSON.
- Built-in interface languages: English, Traditional Chinese, and Simplified Chinese.
- Auto language mode follows the Home Assistant language, with an optional manual override in Budget Book settings.
- Frontend state refreshes after service calls, so newly added, edited, imported, or deleted entries appear without reloading the Home Assistant page.

## Languages

Budget Book stores frontend language files in `www/locales/`:

- `en.json`
- `zh-Hant.json`
- `zh-Hans.json`

To add another language later, add a new JSON file with the same keys, then register the language in `www/app.js`.

## State Refresh

Budget Book reads state from the parent Home Assistant frontend. Since Home Assistant can replace the `hass` object when new states arrive, the panel refreshes the current `hass` reference before polling and schedules short follow-up refreshes after service calls. This avoids stale screens after adding entries, deleting entries, importing data, or changing books.

## Installation

### Release ZIP

Download the latest release ZIP from:

<https://github.com/Im-Tim-mI/Home-Assistant_Budget-Book/releases/latest>

Extract it and copy the `budget_book` folder to:

```bash
/config/custom_components/budget_book
```

Restart Home Assistant after copying the files.

### Manual Installation

1. Create the integration directory in your Home Assistant config folder:

   ```bash
   mkdir -p /config/custom_components/budget_book
   ```

2. Copy this project into that directory. If Git is available on your Home Assistant host, you can clone it directly:

   ```bash
   git clone https://github.com/Im-Tim-mI/Home-Assistant_Budget-Book.git /config/custom_components/budget_book
   ```

3. Restart Home Assistant.

4. Go to Settings -> Devices & services -> Add integration, then search for "Home-Assistant 記帳本", "Budget Book", or "記帳本" and add it.

5. After the integration is added, "記帳本" will appear in the Home Assistant sidebar. Open it to start adding transactions or load the sample data first.

### Updating

If you installed with Git:

```bash
cd /config/custom_components/budget_book
git pull
```

If you installed from a ZIP file, download the latest release ZIP again and replace the existing `budget_book` folder. Restart Home Assistant after updating. If the old panel is still visible, clear the browser/app WebView cache or reload Home Assistant once.

## Services

The integration provides services under the `budget_book` domain. They can be called from automations or Developer Tools, for example:

- `budget_book.add_transaction`
- `budget_book.delete_transaction`
- `budget_book.create_book`
- `budget_book.set_budget`
- `budget_book.add_category`
- `budget_book.add_recurring`
- `budget_book.run_recurring`
- `budget_book.replace_data`

See `services.yaml` for the full field definitions.

## License

This project is licensed under the MIT License.
