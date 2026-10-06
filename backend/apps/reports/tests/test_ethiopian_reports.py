"""The Ethiopian calendar where people see it (Q12): reports, scheduled messages, the
delivery note and the calendar endpoint."""

from datetime import date

import pytest

from apps.core import ethiopian
from apps.notifications.models import NotificationOutbox
from apps.reports import selectors, tasks


def _on(monkeypatch, gregorian: date):
    monkeypatch.setattr("django.utils.timezone.localdate", lambda *a, **k: gregorian)


@pytest.fixture
def owner(staff):
    staff.admin.telegram_id = 1
    staff.admin.save()
    return staff.admin


@pytest.mark.django_db
def test_monthly_report_goes_out_on_the_first_of_an_ethiopian_month(owner, monkeypatch):
    _on(monkeypatch, date(2026, 10, 10))  # Meskerem 30, 2019
    assert tasks.monthly_report() == 0

    _on(monkeypatch, date(2026, 10, 11))  # Tikimt 1, 2019 → report on Meskerem
    assert tasks.monthly_report() == 1

    text = NotificationOutbox.objects.get(event_type="report.monthly").payload["text"]
    assert "Monthly Sales — መስከረም 2019" in text
    assert "መስከረም 1, 2019 – መስከረም 30, 2019 (11/09/2026 – 10/10/2026)" in text


@pytest.mark.django_db
def test_monthly_report_after_pagume_covers_pagume(owner, monkeypatch):
    _on(monkeypatch, date(2026, 9, 11))  # Meskerem 1, 2019 → the month before is Pagume 2018
    tasks.monthly_report()

    text = NotificationOutbox.objects.get(event_type="report.monthly").payload["text"]
    assert "ጳጉሜ 2018" in text and "(06/09/2026 – 10/09/2026)" in text


@pytest.mark.django_db
def test_yearly_report_goes_out_on_meskerem_1(owner, monkeypatch):
    _on(monkeypatch, date(2026, 9, 10))  # Pagume 5, 2018
    assert tasks.yearly_report() == 0

    _on(monkeypatch, date(2026, 9, 11))  # Meskerem 1, 2019
    assert tasks.yearly_report() == 1
    payload = NotificationOutbox.objects.get(event_type="report.yearly").payload
    assert "Yearly Sales — 2018 EC" in payload["text"]
    assert payload["document"]["filename"] == "sales_2018-01-01_2018-13-05_EC.xlsx"


@pytest.mark.django_db
def test_daily_report_title_is_ethiopian_first(owner, monkeypatch):
    _on(monkeypatch, date(2026, 11, 5))
    tasks.daily_report()

    text = NotificationOutbox.objects.get(event_type="report.daily").payload["text"]
    assert text.startswith("📊 <b>Daily Sales — ጥቅምት 26, 2019 (05/11/2026)</b>")


@pytest.mark.django_db
def test_report_api_uses_ethiopian_months_unless_asked(client_for):
    client, _ = client_for("admin")

    ethiopian_month = client.get("/api/v1/reports/sales/", {"period": "month",
                                                            "date": "2026-10-20"}).data
    gregorian_month = client.get("/api/v1/reports/sales/", {"period": "month",
                                                            "date": "2026-10-20",
                                                            "calendar": "gregorian"}).data

    assert (ethiopian_month["from"], ethiopian_month["to"]) == (date(2026, 10, 11),
                                                                date(2026, 11, 9))
    assert ethiopian_month["period_label"].startswith("ጥቅምት 1, 2019 – ጥቅምት 30, 2019")
    assert (gregorian_month["from"], gregorian_month["to"]) == (date(2026, 10, 1),
                                                                date(2026, 10, 31))
    assert client.get("/api/v1/reports/sales/", {"calendar": "lunar"}).status_code == 400


@pytest.mark.django_db
def test_payments_by_ethiopian_month(client_for, staff, accounts, abc):
    from apps.payments.services import record_payment

    record_payment(customer=abc, account=accounts.org, amount="100", method="cash",
                   recorded_by=staff.accountant)
    client, _ = client_for("admin")

    data = client.get("/api/v1/reports/payments/", {"period": "year",
                                                    "group_by": "month"}).data

    today = ethiopian.today()
    assert data["by_period"][0]["label"] == ethiopian.month_label(today.year, today.month)
    assert data["payments"][0]["date_ec"].startswith(str(today).split(",")[0])


@pytest.mark.django_db
def test_calendar_endpoint(client_for):
    client, _ = client_for("salesperson")

    from_gregorian = client.get("/api/v1/calendar/", {"date": "2026-11-05"}).data
    from_ethiopian = client.get("/api/v1/calendar/", {"ec": "2019-02-26"}).data

    assert from_gregorian == from_ethiopian
    assert from_gregorian["ethiopian"] == {"year": 2019, "month": 2, "day": 26,
                                           "month_name": "ጥቅምት", "month_name_en": "Tikimt"}
    assert from_gregorian["display"] == "ጥቅምት 26, 2019 (05/11/2026)"
    assert from_gregorian["ethiopian_month"] == {"first": "2026-10-11", "last": "2026-11-09",
                                                 "days": 30}
    assert client.get("/api/v1/calendar/", {"ec": "2017-13-6"}).status_code == 400


@pytest.mark.django_db
def test_delivery_note_and_statement_show_ethiopian_dates(staff, loc, goods, abc, stock):
    from apps.customers.selectors import customer_statement
    from apps.sales import services
    from apps.sales.pdf import delivery_note_html

    stock(goods.desk, loc.PIA, 3)
    order = services.confirm_order(order=services.create_order(
        customer=abc, branch=loc.PIA, user=staff.sales,
        lines=[{"product": goods.desk, "qty": 1}]), user=staff.sales)

    html = delivery_note_html(order.delivery_notes.get())
    assert ethiopian.format_ec(order.confirmed_at) in html
    row = customer_statement(abc, staff.accountant)["rows"][0]
    assert row.date_ec.startswith(ethiopian.format_ec(order.confirmed_at))


def test_report_period_helper_stays_gregorian_for_days_and_weeks():
    wednesday = date(2026, 10, 7)
    assert selectors.period_range("day", wednesday) == (wednesday, wednesday)
    assert selectors.period_range("week", wednesday) == (date(2026, 10, 5), date(2026, 10, 11))
