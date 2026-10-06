"""Scheduled reports to the owner (admins) by Telegram (BUILD_PHASES.md 4.4)."""

import base64
from datetime import date, timedelta
from types import SimpleNamespace

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.notifications.services import notify
from apps.notifications.templates import etb

from . import excel, selectors

# Reports run as the owner sees them: every figure, Personal included.
OWNER_VIEW = SimpleNamespace(pk=None, role="admin", home_location_id=None,
                             has_erp_permission=lambda permission: True)


def _top(items, key, limit=5, fmt=etb):
    return " · ".join(f"{item[key]} {fmt(item['sales'])}" for item in items[:limit]) or "—"


def report_text(title: str, data: dict, *, outstanding=None, collected=None) -> str:
    """The plan's message format, e.g. "📊 Daily Sales — 03/10/2026"."""
    first, last = data["from"], data["to"]
    when = (first.strftime("%d/%m/%Y") if first == last
            else f"{first.strftime('%d/%m/%Y')} – {last.strftime('%d/%m/%Y')}")
    received = data["received"]
    lines = [
        f"📊 <b>{title} — {when}</b>",
        f"Total sales: {etb(data['net_sales'])} ({data['transactions']} sales)"
        + (f", returns {etb(data['returns'])}" if data["returns"] != "0.00" else ""),
        f"Paid: {etb(data['paid'])} · Credit: {etb(data['credit'])}",
        f"Official receipt: {etb(data['official_receipt'])} · No receipt: "
        f"{etb(data['no_receipt'])}",
        f"Received → Organization: {etb(received['organization'])} · Personal: "
        f"{etb(received['personal'])}",
    ]
    if outstanding is not None:
        lines.append(f"Outstanding credit (all customers): {etb(outstanding)}")
    if collected is not None:
        lines.append(f"Credit collected: {etb(collected)}")
    lines += [
        "",
        f"By branch: {_top(data['by_branch'], 'branch')}",
        f"By salesperson: {_top(data['by_salesperson'], 'salesperson')}",
        "Products sold: " + (", ".join(f"{p['code']} ×{p['qty']}"
                                       for p in data["best_sellers"]) or "—"),
    ]
    return "\n".join(lines)


def _send(kind: str, title: str, first: date, last: date, *, with_credit: bool,
          attach: bool) -> int:
    data = selectors.sales_report(OWNER_VIEW, first, last)
    credit = selectors.credit_report(OWNER_VIEW, first, last) if with_credit else None
    message = {"text": report_text(title, data,
                                   outstanding=credit["outstanding_total"] if credit else None,
                                   collected=credit["credit_collected"] if credit else None),
               "buttons": []}
    if attach:
        message["document"] = {
            "filename": excel.filename("sales", data),
            "content_b64": base64.b64encode(excel.workbook_bytes("sales", data)).decode()}
    with transaction.atomic():
        return notify(f"report.{kind}", None, message=message)


@shared_task
def daily_report() -> int:
    """20:00 every day: today's figures."""
    today = timezone.localdate()
    return _send("daily", "Daily Sales", today, today, with_credit=False, attach=False)


@shared_task
def weekly_report() -> int:
    """Saturday 20:00: Monday to today, with outstanding credit and an Excel file."""
    first, _ = selectors.period_range("week")
    return _send("weekly", "Weekly Sales", first, timezone.localdate(), with_credit=True,
                 attach=True)


@shared_task
def monthly_report() -> int:
    """1st of the month 08:00: the previous month."""
    first, last = selectors.period_range("month",
                                         timezone.localdate().replace(day=1) - timedelta(days=1))
    return _send("monthly", "Monthly Sales", first, last, with_credit=True, attach=True)


@shared_task
def yearly_report() -> int:
    """1 January 08:00: the previous year, with a month-by-month sheet."""
    last_year = timezone.localdate().year - 1
    return _send("yearly", "Yearly Sales", date(last_year, 1, 1), date(last_year, 12, 31),
                 with_credit=True, attach=True)
