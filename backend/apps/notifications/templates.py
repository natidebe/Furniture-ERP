"""Telegram message texts and buttons, in one place for the API's notifications and the bot.

Every function returns {"text": str, "buttons": [[button, ...], ...]}; text is Telegram HTML.
Button callback data: "<object>:<action>:<id>", handled by the bot (bot/handlers).
"""

from decimal import Decimal
from html import escape


def money(value) -> str:
    """100000 → "100,000"; 1500.5 → "1,500.50"."""
    if value is None:
        return "—"
    text = f"{Decimal(value):,.2f}"
    return text[:-3] if text.endswith(".00") else text


def etb(value) -> str:
    return f"{money(value)} ETB"


def _lines(request) -> str:
    return "\n".join(f"• {ln.qty_requested - ln.qty_released} × {escape(ln.product.code)} "
                     f"{escape(ln.product.name)}" for ln in request.lines.select_related("product")
                     if ln.qty_requested > ln.qty_released)


def stock_request_card(request, *, title="📦 New stock request") -> dict:
    who = escape(request.customer.name) if request.customer else "branch stock"
    text = (f"<b>{title}</b> — <code>{request.number}</code>\n"
            f"From: {escape(request.requesting_location.name)}\n"
            f"For: {who}"
            + (f" ({escape(request.reference)})" if request.reference else "")
            + f"\nSalesperson: {escape(request.salesperson.full_name)}\n"
            + (f"Transaction: <code>{request.transaction_number}</code>\n"
               if request.transaction_number != request.number else "")
            + f"\n{_lines(request)}"
            + (f"\n\nNote: {escape(request.notes)}" if request.notes else ""))
    buttons = []
    if request.status == "pending":
        buttons.append([{"text": "Acknowledge", "callback_data": f"req:ack:{request.pk}"},
                        {"text": "Reject", "callback_data": f"req:rej:{request.pk}"}])
    if request.status in ("acknowledged", "partially_released"):
        buttons.append([{"text": "Release", "callback_data": f"req:rel:{request.pk}"}])
    return {"text": text, "buttons": buttons}


def stock_request_update(request, what: str, release=None) -> dict:
    text = f"📦 <code>{request.number}</code> {what}"
    if release is not None:
        items = ", ".join(f"{ln.qty} × {escape(ln.product.code)}"
                          for ln in release.lines.select_related("product"))
        text += f"\n{release.number}: {items}"
        if release.transfer_id:
            text += f"\nOn its way to {escape(request.requesting_location.name)} " \
                    f"(<code>{release.transfer.number}</code>) — receive it when it arrives."
    if request.close_reason and what in ("was rejected", "was cancelled"):
        text += f"\nReason: {escape(request.close_reason)}"
    return {"text": text, "buttons": []}


def transfer_sent(transfer) -> dict:
    items = "\n".join(f"• {ln.qty_sent} × {escape(ln.product.code)}"
                      + (f" ({ln.condition})" if ln.condition != "new" else "")
                      for ln in transfer.lines.select_related("product"))
    return {"text": (f"🚚 <b>Stock on its way</b> — <code>{transfer.number}</code>\n"
                     f"From {escape(transfer.from_location.name)} to "
                     f"{escape(transfer.to_location.name)}\n{items}"),
            "buttons": [[{"text": "Received everything",
                          "callback_data": f"tr:recv:{transfer.pk}"}]]}


def transfer_discrepancy(transfer) -> dict:
    return {"text": (f"⚠️ <b>Short delivery</b> — <code>{transfer.number}</code> at "
                     f"{escape(transfer.to_location.name)}\n"
                     f"{escape(transfer.discrepancy_note)}"), "buttons": []}


def payment_to_verify(payment) -> dict:
    return {"text": (f"💳 <b>Payment to verify</b> — <code>{payment.number}</code>\n"
                     f"{escape(payment.customer.name)}: {etb(payment.amount)}\n"
                     f"Account: {escape(payment.account.name)} ({payment.account.kind})"
                     + (f"\nReceipt: {escape(payment.receipt_number)}"
                        if payment.receipt_number else "")
                     + f"\nRecorded by {escape(payment.recorded_by.full_name)}"),
            "buttons": [[{"text": "Verify", "callback_data": f"pay:ok:{payment.pk}"},
                         {"text": "Reject", "callback_data": f"pay:rej:{payment.pk}"}]]}


def payment_rejected(payment) -> dict:
    return {"text": (f"❌ Payment <code>{payment.number}</code> ({etb(payment.amount)}, "
                     f"{escape(payment.customer.name)}) was rejected.\n"
                     f"Reason: {escape(payment.close_reason)}"), "buttons": []}


def adjustment_proposed(adjustment) -> dict:
    sign = "+" if adjustment.qty_delta > 0 else ""
    return {"text": (f"📝 <b>Stock adjustment to approve</b> — <code>{adjustment.number}</code>\n"
                     f"{escape(adjustment.product.code)} at {adjustment.location.code}: "
                     f"{sign}{adjustment.qty_delta} ({adjustment.condition}, "
                     f"{adjustment.reason})"
                     + (f"\n{escape(adjustment.note)}" if adjustment.note else "")
                     + f"\nProposed by {escape(adjustment.proposed_by.full_name)}"),
            "buttons": []}


def order_update(order, what: str) -> dict:
    return {"text": f"🧾 Sale <code>{order.number}</code> ({escape(order.customer.name)}) {what}",
            "buttons": []}


def low_stock(product, total_new: int) -> dict:
    """The client's example format."""
    unit = product.unit.symbol
    return {"text": (f"⚠️ <b>LOW STOCK</b>\n{escape(product.name)} ({escape(product.code)})\n"
                     f"Current stock: {total_new} {unit}\nMinimum: {product.min_stock} {unit}"),
            "buttons": []}


def stock_mismatch(count: int) -> dict:
    return {"text": (f"🚨 <b>Stock check</b>: {count} balance(s) do not match the movement "
                     f"history. Run <code>rebuild_stock_balances --check</code> and "
                     f"investigate before fixing."), "buttons": []}


def product_card(row: dict) -> str:
    """The `VC-001` lookup: name, price, stock per location and total."""
    lines = [f"<b>{escape(row['name'])}</b> — <code>{escape(row['code'])}</code>",
             f"Price: {etb(row['selling_price'])}"]
    if row.get("wholesale_price"):
        lines.append(f"Wholesale: {etb(row['wholesale_price'])}")
    for code, qty in row["stock"].items():
        if code != "TRANSIT":
            lines.append(f"{escape(code)}: {qty}")
    if row.get("in_transit"):
        lines.append(f"In transit: {row['in_transit']}")
    lines.append(f"<b>Total: {row['total']}</b>")
    return "\n".join(lines)
