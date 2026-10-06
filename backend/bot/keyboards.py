"""Menus and buttons. Main menus follow the client's layout ("Telegram Interface")."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

NEW_SALE = "🛒 New Sale"
REQUEST_STOCK = "📦 Request Stock"
CHECK_STOCK = "🔍 Check Stock"
CUSTOMERS = "👤 Customers"
CREDIT = "💳 Credit"
MY_ORDERS = "📋 My Orders"
MY_SALES = "📊 My Sales"
INCOMING = "🚚 Incoming Stock"
STOCK_REQUESTS = "📦 Stock Requests"
PAWLOS_STOCK = "🏭 Pawlos Stock"
RELEASE_STOCK = "🚚 Release Stock"
STOCK_HISTORY = "📋 Stock History"
SALES = "💰 Sales"
PAYMENTS = "💳 Payments"
CREDIT_REPORT = "📒 Credit"
STOCK = "📦 Stock"
REPORTS = "📊 Reports"
EXPORT = "📄 Export Excel"

MENUS = {
    "salesperson": [[NEW_SALE, REQUEST_STOCK], [CHECK_STOCK, CUSTOMERS], [CREDIT, MY_ORDERS],
                    [MY_SALES, INCOMING]],
    "storekeeper": [[STOCK_REQUESTS, PAWLOS_STOCK], [RELEASE_STOCK, STOCK_HISTORY]],
    "accountant": [[SALES, PAYMENTS], [CREDIT_REPORT, STOCK], [REPORTS, EXPORT]],
}
# Admin sees everything (the client's "Admin sees everything").
MENUS["admin"] = [[SALES, PAYMENTS], [CREDIT_REPORT, STOCK], [REPORTS, EXPORT],
                  [STOCK_REQUESTS, STOCK_HISTORY], [CHECK_STOCK, NEW_SALE]]

ALL_BUTTONS = {label for menu in MENUS.values() for row in menu for label in row}


def main_menu(role: str) -> ReplyKeyboardMarkup:
    rows = MENUS.get(role, [[CHECK_STOCK]])
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
                               resize_keyboard=True)


def inline(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    """rows of (text, callback_data); a value starting with http(s) becomes a link button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, url=value) if value.startswith("http")
         else InlineKeyboardButton(text=text, callback_data=value) for text, value in row]
        for row in rows])


def request_buttons(request: dict) -> InlineKeyboardMarkup | None:
    status, rid = request["status"], request["id"]
    if status == "pending":
        return inline([[("Acknowledge", f"req:ack:{rid}"), ("Reject", f"req:rej:{rid}")]])
    if status in ("acknowledged", "partially_released"):
        return inline([[("Release", f"req:rel:{rid}")]])
    return None


def qty_buttons(line: dict) -> InlineKeyboardMarkup:
    remaining = line["remaining"]
    row = [(f"All {remaining}", f"rq:{remaining}")]
    if remaining > 1:
        row.append(("Skip", "rq:0"))
    return inline([row])


def destination_buttons(has_customer: bool) -> InlineKeyboardMarkup:
    row = [("To branch", "rd:branch")]
    if has_customer:
        row.append(("Customer pickup", "rd:customer_pickup"))
    return inline([row])


CONFIRM = inline([[("✅ Confirm", "rc:yes"), ("✖ Cancel", "rc:no")]])
REPORT_PERIODS = inline([[("Today", "rp:day"), ("This week", "rp:week")],
                         [("This month", "rp:month"), ("This year", "rp:year")]])
EXPORT_PERIODS = inline([[("Today", "rx:day"), ("This week", "rx:week")],
                         [("This month", "rx:month"), ("This year", "rx:year")]])
