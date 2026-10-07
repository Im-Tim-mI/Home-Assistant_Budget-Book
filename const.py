"""Constants for Budget Book integration."""

DOMAIN = "budget_book"
PLATFORMS = ["sensor"]

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_data"

# Services
SERVICE_ADD_TRANSACTION = "add_transaction"
SERVICE_DELETE_TRANSACTION = "delete_transaction"
SERVICE_CREATE_BOOK = "create_book"
SERVICE_DELETE_BOOK = "delete_book"
SERVICE_RENAME_BOOK = "rename_book"
SERVICE_SET_BUDGET = "set_budget"
SERVICE_ADD_CATEGORY = "add_category"
SERVICE_DELETE_CATEGORY = "delete_category"
SERVICE_ADD_RECURRING = "add_recurring"
SERVICE_DELETE_RECURRING = "delete_recurring"
SERVICE_RUN_RECURRING = "run_recurring"
SERVICE_LOAD_SAMPLE = "load_sample"
SERVICE_CLEAR_ALL = "clear_all"
SERVICE_REPLACE_DATA = "replace_data"

# Transaction types
TYPE_INCOME = "income"
TYPE_EXPENSE = "expense"

# Signal
SIGNAL_UPDATE = f"{DOMAIN}_update"

# Default categories (created on first run)
DEFAULT_EXPENSE_CATEGORIES = [
    {"id": "food", "name": "餐飲", "icon": "mdi:silverware-fork-knife", "color": "#E67E22"},
    {"id": "transport", "name": "交通", "icon": "mdi:bus", "color": "#3498DB"},
    {"id": "shopping", "name": "購物", "icon": "mdi:shopping", "color": "#9B59B6"},
    {"id": "entertainment", "name": "娛樂", "icon": "mdi:gamepad-variant", "color": "#E74C3C"},
    {"id": "household", "name": "家用", "icon": "mdi:home", "color": "#16A085"},
    {"id": "medical", "name": "醫療", "icon": "mdi:hospital-box", "color": "#C0392B"},
    {"id": "education", "name": "教育", "icon": "mdi:school", "color": "#2980B9"},
    {"id": "subscription", "name": "訂閱", "icon": "mdi:repeat", "color": "#8E44AD"},
    {"id": "rent", "name": "房租", "icon": "mdi:home-city", "color": "#7F8C8D"},
    {"id": "utility", "name": "水電瓦斯", "icon": "mdi:flash", "color": "#F39C12"},
    {"id": "other", "name": "其他", "icon": "mdi:dots-horizontal", "color": "#95A5A6"},
]

DEFAULT_INCOME_CATEGORIES = [
    {"id": "salary", "name": "薪資", "icon": "mdi:cash-multiple", "color": "#27AE60"},
    {"id": "bonus", "name": "獎金", "icon": "mdi:gift", "color": "#16A085"},
    {"id": "investment", "name": "投資", "icon": "mdi:chart-line", "color": "#2980B9"},
    {"id": "side", "name": "副業", "icon": "mdi:briefcase-plus", "color": "#8E44AD"},
    {"id": "income_other", "name": "其他收入", "icon": "mdi:cash-plus", "color": "#95A5A6"},
]
