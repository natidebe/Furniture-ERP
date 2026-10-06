"""Scheduled reports to the owner (admins) by Telegram (BUILD_PHASES.md 4.4)."""

import base64
from datetime import date
from types import SimpleNamespace

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.core import ethiopian
from apps.notifications.services import notify
from apps.notifications.templates import etb

from . import excel, selectors

# Reports run as the owner sees them: every figure, Personal included.
OWNER_VIEW = SimpleNamespace(pk=None, role="admin", home_location_id=None,
                             has_erp_permission=lambda permission: True)


def _top(items, key, limit=5, fmt=etb):
    return " · ".join(f"{item[key]} {fmt(item['sales'])}" for item in items[:limit]) or "—"


def report_text(title: str, data: dict, *, outstanding=None, collected=None) -> str:
    """The plan's message format, Ethiopian date first (Q12), e.g.
    "📊 Daily Sales — ጥቅምት 26, 2019 (05/11/2026)"."""
    when = data["period_label"]
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
    """Runs every morning at 08:00; on the 1st of an Ethiopian month it sends the previous
    Ethiopian month (Q12). Returns the number of messages queued (0 on other days)."""
    today = ethiopian.today()
    if today.day != 1:
        return 0
    year, month = ethiopian.previous_month(today)
    first, last = ethiopian.month_range(year, month)
    return _send("monthly", f"Monthly Sales — {ethiopian.month_label(year, month)}", first,
                 last, with_credit=True, attach=True)


@shared_task
def yearly_report() -> int:
    """Runs every morning at 08:00; on Meskerem 1 it sends the Ethiopian year just ended,
    with a sheet per Ethiopian month (13, Pagume included)."""
    today = ethiopian.today()
    if (today.month, today.day) != (1, 1):
        return 0
    first, last = ethiopian.year_range(today.year - 1)
    return _send("yearly", f"Yearly Sales — {today.year - 1} EC", first, last,
                 with_credit=True, attach=True)
