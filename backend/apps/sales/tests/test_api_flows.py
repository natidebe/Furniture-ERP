"""The Phase 3 definition-of-done flows, over the API as the web page will call it."""

from decimal import Decimal

import pytest

from apps.accounts.models import ERPPermission
from apps.accounts.services import set_erp_permissions
from apps.inventory.selectors import balance_mismatches

D = Decimal


@pytest.fixture
def as_user(api_client):
    def _as(user):
        api_client.force_authenticate(user)
        return api_client
    return _as


@pytest.mark.django_db
def test_walk_in_flow(as_user, staff, loc, goods, walk_in, accounts, stock):
    """create (with payment now) → confirm → delivery note → paid."""
    stock(goods.desk, loc.PIA, 5)
    staff.sales.allowed_payment_accounts.add(accounts.org)
    client = as_user(staff.sales)

    created = client.post("/api/v1/orders/", {
        "customer": walk_in.pk, "lines": [{"product": goods.desk.pk, "qty": 1}],
        "payment": {"account": accounts.org.pk, "amount": "20000.00", "method": "cash"}},
        format="json")
    assert created.status_code == 201, created.data
    assert created.data["fulfillment_status"] == "draft"
    assert created.data["branch_code"] == "PIA"
    assert created.data["payment_status"] == "paid"

    confirmed = client.post(f"/api/v1/orders/{created.data['id']}/confirm/")
    assert confirmed.status_code == 200, confirmed.data
    assert confirmed.data["fulfillment_status"] == "released"
    note = confirmed.data["delivery_notes"][0]
    assert note["number"].startswith("DN-")
    assert note["lines"] == [{"product_code": "DS-003", "product_name": "Manager desk",
                              "qty": 1}]


@pytest.mark.django_db
def test_pawlos_flow(as_user, staff, loc, goods, abc, accounts, stock, balance):
    """order → stock request → release → transfer received → branch handover → payment."""
    stock(goods.chair, loc.PAW, 40)
    order = as_user(staff.sales).post("/api/v1/orders/", {
        "customer": abc.pk, "channel": "phone",
        "lines": [{"product": goods.chair.pk, "qty": 10, "source_location": loc.PAW.pk}]},
        format="json").data
    assert order["lines"][0]["unit_price"] == "4500.00"  # reseller → wholesale (D11)
    order = as_user(staff.sales).post(f"/api/v1/orders/{order['id']}/confirm/").data
    request = order["stock_requests"][0]

    store = as_user(staff.store)
    store.post(f"/api/v1/stock-requests/{request['id']}/acknowledge/")
    detail = store.get(f"/api/v1/stock-requests/{request['id']}/").data
    assert detail["transaction_number"] == order["number"]
    release = store.post(f"/api/v1/stock-requests/{request['id']}/release/", {
        "destination_type": "branch",
        "lines": [{"line_id": detail["lines"][0]["id"], "qty": 10}]}, format="json").data

    sales_client = as_user(staff.sales)
    transfers = sales_client.get("/api/v1/transfers/?status=in_transit").data["results"]
    assert transfers[0]["number"] == release["transfer_number"]
    sales_client.post(f"/api/v1/transfers/{transfers[0]['id']}/receive/", {}, format="json")
    order = sales_client.get(f"/api/v1/orders/{order['id']}/").data
    assert order["lines"][0]["qty_awaiting"] == 10

    handed = sales_client.post(f"/api/v1/orders/{order['id']}/release-from-branch/", {
        "lines": [{"line_id": order["lines"][0]["id"], "qty": 10}]}, format="json")
    assert handed.status_code == 200, handed.data
    assert handed.data["fulfillment_status"] == "released"

    paid = as_user(staff.accountant).post("/api/v1/payments/", {
        "customer": abc.pk, "account": accounts.org.pk, "amount": "45000.00",
        "method": "bank", "allocations": [{"order": order["id"], "amount": "45000.00"}]},
        format="json")
    assert paid.status_code == 201, paid.data
    assert paid.data["status"] == "verified"
    assert balance(goods.chair, loc.PIA) == (0, 0)
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_phone_order_with_partial_payments_and_credit(as_user, staff, loc, goods, abc,
                                                     accounts, stock):
    stock(goods.chair, loc.PAW, 40)
    client = as_user(staff.accountant)
    order = client.post("/api/v1/orders/", {
        "customer": abc.pk, "branch": loc.PIA.pk, "channel": "phone",
        "lines": [{"product": goods.chair.pk, "qty": 20, "source_location": loc.PAW.pk}]},
        format="json").data
    assert order["fulfillment_status"] == "pending"
    client.post(f"/api/v1/orders/{order['id']}/confirm/")
    for amount, account in (("40000.00", accounts.org), ("20000.00", accounts.personal)):
        client.post("/api/v1/payments/", {
            "customer": abc.pk, "account": account.pk, "amount": amount, "method": "bank",
            "allocations": [{"order": order["id"], "amount": amount}]}, format="json")

    history = client.get(f"/api/v1/orders/{order['id']}/payments/").data

    assert (history["total"], history["paid"], history["remaining"]) == (
        "90000.00", "60000.00", "30000.00")
    assert history["payment_status"] == "partial"
    assert [p["account_kind"] for p in history["payments"]] == ["organization", "personal"]
    balance = client.get(f"/api/v1/customers/{abc.pk}/balance/").data
    assert balance["outstanding"] == "30000.00"


@pytest.mark.django_db
def test_accountant_verifies_rejects_and_reverses(as_user, staff, loc, goods, abc, accounts,
                                                  stock):
    stock(goods.desk, loc.PIA, 5)
    staff.sales.allowed_payment_accounts.add(accounts.org)
    sales_client = as_user(staff.sales)
    order = sales_client.post("/api/v1/orders/", {
        "customer": abc.pk, "lines": [{"product": goods.desk.pk, "qty": 2}]},
        format="json").data
    sales_client.post(f"/api/v1/orders/{order['id']}/confirm/")
    ids = [sales_client.post("/api/v1/payments/", {
        "customer": abc.pk, "account": accounts.org.pk, "amount": "1000.00", "method": "bank",
        "allocations": [{"order": order["id"], "amount": "1000.00"}]},
        format="json").data["id"] for _ in range(3)]

    acct = as_user(staff.accountant)
    queue = acct.get("/api/v1/payments/?status=unverified").data
    assert queue["count"] == 3
    verified = acct.post(f"/api/v1/payments/{ids[0]}/verify/").data
    assert (verified["status"], verified["verified_by_name"]) == (
        "verified", staff.accountant.full_name)
    rejected = acct.post(f"/api/v1/payments/{ids[1]}/reject/", {"reason": "Not in bank"},
                         format="json").data
    assert (rejected["status"], rejected["closed_by_name"]) == (
        "rejected", staff.accountant.full_name)
    assert acct.post(f"/api/v1/payments/{ids[2]}/reverse/", {"reason": "Duplicate"},
                     format="json").data["status"] == "reversed"
    audit = acct.get("/api/v1/audit/?model=payments.Payment").data
    assert {r["action"] for r in audit["results"]} >= {
        "payment_recorded", "payment_verified", "payment_rejected", "payment_reversed"}

    sales_view = as_user(staff.sales).post(f"/api/v1/payments/{ids[0]}/verify/")
    assert sales_view.status_code == 403


@pytest.mark.django_db
def test_personal_amounts_hidden_from_a_user_without_the_permission(as_user, staff, loc,
                                                                   goods, abc, accounts,
                                                                   stock, make_user):
    stock(goods.desk, loc.PIA, 5)
    acct = as_user(staff.accountant)
    order = acct.post("/api/v1/orders/", {"customer": abc.pk, "branch": loc.PIA.pk,
                                          "lines": [{"product": goods.desk.pk, "qty": 1}]},
                      format="json").data
    acct.post(f"/api/v1/orders/{order['id']}/confirm/")
    acct.post("/api/v1/payments/", {
        "customer": abc.pk, "account": accounts.personal.pk, "amount": "5000.00",
        "method": "cash", "allocations": [{"order": order["id"], "amount": "5000.00"}]},
        format="json")

    restricted = make_user(role="accountant")
    set_erp_permissions(restricted, [ERPPermission.VERIFY_PAYMENTS])
    rows = as_user(restricted).get("/api/v1/payments/").data["results"]

    assert rows[0]["amount"] is None and rows[0]["hidden"] is True
    assert rows[0]["account_kind"] == "personal"
    assert as_user(staff.accountant).get("/api/v1/payments/").data["results"][0][
        "amount"] == "5000.00"


@pytest.mark.django_db
def test_salesperson_sees_only_own_orders(as_user, staff, loc, goods, walk_in, make_user):
    mine = as_user(staff.sales).post("/api/v1/orders/", {
        "customer": walk_in.pk, "lines": [{"product": goods.desk.pk, "qty": 1}]},
        format="json").data
    other = make_user(role="salesperson", home_location=loc.PIA)
    as_user(other).post("/api/v1/orders/", {
        "customer": walk_in.pk, "lines": [{"product": goods.desk.pk, "qty": 1}]},
        format="json")

    listed = as_user(staff.sales).get("/api/v1/orders/").data

    assert [o["number"] for o in listed["results"]] == [mine["number"]]
    assert as_user(staff.accountant).get("/api/v1/orders/").data["count"] == 2


@pytest.mark.django_db
def test_storekeeper_cannot_create_sales(as_user, staff, walk_in, goods):
    response = as_user(staff.store).post("/api/v1/orders/", {
        "customer": walk_in.pk, "lines": [{"product": goods.desk.pk, "qty": 1}]},
        format="json")
    assert response.status_code == 403


@pytest.mark.django_db
def test_void_and_reissue_over_the_api(as_user, staff, loc, goods, abc, stock):
    stock(goods.desk, loc.PIA, 5)
    client = as_user(staff.admin)
    order = client.post("/api/v1/orders/", {"customer": abc.pk, "branch": loc.PIA.pk,
                                            "lines": [{"product": goods.desk.pk, "qty": 1}]},
                        format="json").data
    client.post(f"/api/v1/orders/{order['id']}/confirm/")

    assert client.post(f"/api/v1/orders/{order['id']}/void/", {},
                       format="json").status_code == 400  # reason required
    voided = client.post(f"/api/v1/orders/{order['id']}/void/", {"reason": "Wrong desk"},
                         format="json")
    assert voided.data["fulfillment_status"] == "voided"
    fixed = client.post("/api/v1/orders/", {
        "customer": abc.pk, "branch": loc.PIA.pk, "replaces": order["id"],
        "lines": [{"product": goods.cabinet.pk, "qty": 1}]}, format="json").data
    assert fixed["replaces"] == order["number"]
    assert client.get(f"/api/v1/orders/{order['id']}/").data["replaced_by"] == fixed["number"]


@pytest.mark.django_db
def test_settings_discount_limit(as_user, staff):
    assert as_user(staff.sales).get("/api/v1/settings/").data[
        "max_salesperson_discount_pct"] == "0.00"
    assert as_user(staff.sales).patch("/api/v1/settings/", {
        "max_salesperson_discount_pct": "10"}, format="json").status_code == 400

    changed = as_user(staff.admin).patch("/api/v1/settings/",
                                         {"max_salesperson_discount_pct": "7.5"},
                                         format="json")
    assert changed.status_code == 200
    assert changed.data["max_salesperson_discount_pct"] == "7.50"


@pytest.mark.django_db
def test_delivery_note_html_has_number_and_lines(staff, loc, goods, walk_in, stock):
    from apps.sales import services
    from apps.sales.pdf import delivery_note_html

    stock(goods.desk, loc.PIA, 5)
    order = services.create_order(customer=walk_in, branch=loc.PIA, user=staff.accountant,
                                  lines=[{"product": goods.desk, "qty": 2}])
    order = services.confirm_order(order=order, user=staff.accountant)
    note = order.delivery_notes.get()

    html = delivery_note_html(note)

    assert note.number in html and order.number in html
    assert "DS-003" in html and "40,000.00" in html


@pytest.mark.django_db
def test_delivery_note_pdf(as_user, staff, loc, goods, walk_in, stock):
    pytest.importorskip("weasyprint", exc_type=OSError)
    from apps.sales import services

    stock(goods.desk, loc.PIA, 5)
    order = services.confirm_order(order=services.create_order(
        customer=walk_in, branch=loc.PIA, user=staff.accountant,
        lines=[{"product": goods.desk, "qty": 1}]), user=staff.accountant)
    note = order.delivery_notes.get()

    # The accountant created this sale, so a salesperson may not see it (D9).
    assert as_user(staff.sales).get(f"/api/v1/delivery-notes/{note.pk}/pdf/").status_code == 404
    response = as_user(staff.accountant).get(f"/api/v1/delivery-notes/{note.pk}/pdf/")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


@pytest.mark.django_db
def test_owing_filter_lists_unpaid_and_partly_paid_sales(as_user, staff, loc, goods, abc,
                                                         walk_in, accounts, stock):
    from apps.payments import services as payments
    from apps.sales import services as sales

    stock(goods.desk, loc.PIA, 5)

    def sale(customer):
        order = sales.create_order(customer=customer, branch=loc.PIA, user=staff.accountant,
                                   lines=[{"product": goods.desk, "qty": 1}])
        return sales.confirm_order(order=order, user=staff.accountant)

    unpaid, partial, paid = sale(abc), sale(abc), sale(abc)
    for order, amount in ((partial, "5000"), (paid, "20000")):
        payments.record_payment(customer=abc, account=accounts.org, amount=D(amount),
                                method="bank", recorded_by=staff.accountant,
                                receipt_number=f"R-{order.pk}",
                                allocations=[{"order": order, "line": None, "amount": D(amount)}])
    draft = sales.create_order(customer=walk_in, branch=loc.PIA, user=staff.accountant,
                               lines=[{"product": goods.desk, "qty": 1}])
    client = as_user(staff.accountant)

    owing = {o["id"] for o in client.get("/api/v1/orders/", {"owing": "true"}).data["results"]}

    assert owing == {unpaid.pk, partial.pk}
    assert draft.pk not in owing
