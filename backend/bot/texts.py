"""Reply texts built from API data (Telegram HTML)."""

from decimal import Decimal
from html import escape


def etb(value) -> str:
    if value is None:
        return "—"
    text = f"{Decimal(str(value)):,.2f}"
    return (text[:-3] if text.endswith(".00") else text) + " ETB"


def product_card(row: dict) -> str:
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


def request_card(r: dict) -> str:
    lines = "\n".join(f"• {ln['qty_remaining']} of {ln['qty_requested']} × "
                      f"{escape(ln['product_code'])} {escape(ln['product_name'])}"
                      for ln in r["lines"])
    who = escape(r.get("customer_name") or "branch stock")
    return (f"📦 <code>{r['number']}</code> — {r['status'].replace('_', ' ')}\n"
            f"From {escape(r['requesting_location_code'])} · for {who}"
            + (f" ({escape(r['reference'])})" if r.get("reference") else "")
            + f"\nSalesperson: {escape(r['salesperson_name'])}\n{lines}")


def payment_card(p: dict) -> str:
    return (f"💳 <code>{p['number']}</code> — {escape(p['customer_name'])}\n"
            f"{etb(p['amount'])} · {escape(p['account_name'] or p['account_kind'])} "
            f"({p['account_kind']})"
            + (f"\nReceipt: {escape(p['receipt_number'])}" if p.get("receipt_number") else "")
            + f"\nRecorded by {escape(p['recorded_by_name'])}")


def order_line(o: dict) -> str:
    return (f"<code>{o['number']}</code> {escape(o['customer_name'])} — {etb(o['total'])}, "
            f"{o['fulfillment_status'].replace('_', ' ')}, {o['payment_status']}")


def sales_summary(title: str, r: dict) -> str:
    received = r.get("received") or {}
    parts = [f"📊 <b>{title}</b> ({r['from']}" + (f" – {r['to']}" if r["to"] != r["from"]
                                                  else "") + ")",
             f"Total sales: {etb(r['net_sales'])} ({r['transactions']} sales)"]
    if r.get("paid") is not None:
        parts.append(f"Paid: {etb(r['paid'])} · Credit: {etb(r['credit'])}")
    parts.append(f"Official receipt: {etb(r['official_receipt'])} · No receipt: "
                 f"{etb(r['no_receipt'])}")
    if received:
        parts.append(f"Received → Organization: {etb(received.get('organization'))} · "
                     f"Personal: {etb(received.get('personal'))}")
    if r.get("by_branch"):
        parts.append("By branch: " + " · ".join(f"{b['branch']} {etb(b['sales'])}"
                                                for b in r["by_branch"]))
    if r.get("best_sellers"):
        parts.append("Top: " + ", ".join(f"{p['code']} ×{p['qty']}"
                                         for p in r["best_sellers"][:5]))
    return "\n".join(parts)


NOT_LINKED = ("This Telegram account is not linked yet.\n"
              "In the web app open <b>My profile → Get link code</b>, then send "
              "<code>/start CODE</code> here.")
