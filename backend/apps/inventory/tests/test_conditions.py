"""Display and damaged stock (D15)."""

import random
from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.core.exceptions import BusinessRuleError
from apps.inventory import services
from apps.inventory.models import StockBalance, StockConditionChange
from apps.inventory.selectors import balance_mismatches, low_stock_products
from apps.requests import services as requests
from apps.sales import services as sales
from tests.factories import CustomerFactory, ProductFactory


def counts(product, location):
    bal = StockBalance.objects.get(product=product, location=location)
    return {"on_hand": bal.on_hand, "new": bal.new, "display": bal.display,
            "damaged": bal.damaged, "available": bal.available}


@pytest.mark.django_db
def test_putting_a_piece_on_display_keeps_the_total(staff, loc, product, stock):
    stock(product, loc.PIA, 5)

    change = services.change_condition(product=product, location=loc.PIA, qty=1,
                                       from_condition="new", to_condition="display",
                                       user=staff.sales, reason="Showroom sample")

    assert change.number.startswith("CC-")
    assert counts(product, loc.PIA) == {"on_hand": 5, "new": 4, "display": 1, "damaged": 0,
                                        "available": 4}
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_display_and_damaged_pieces_are_never_sold_as_new_or_reserved(staff, loc, product,
                                                                      stock):
    stock(product, loc.PAW, 3)
    services.change_condition(product=product, location=loc.PAW, qty=2,
                              from_condition="new", to_condition="damaged",
                              user=staff.store, reason="Scratched in container")

    with pytest.raises(BusinessRuleError) as exc:
        requests.create_stock_request(requesting_location=loc.PIA, source_location=loc.PAW,
                                      lines=[{"product": product, "qty": 2}],
                                      salesperson=staff.sales)
    assert exc.value.code == "insufficient_stock"


@pytest.mark.django_db
def test_only_staff_at_the_location_change_its_stock(staff, loc, product, stock):
    stock(product, loc.PAW, 3)
    with pytest.raises(BusinessRuleError) as exc:
        services.change_condition(product=product, location=loc.PAW, qty=1,
                                  from_condition="new", to_condition="damaged",
                                  user=staff.sales, reason="x")
    assert exc.value.code == "wrong_location"


@pytest.mark.django_db
def test_condition_changes_need_stock_and_a_reason(staff, loc, product, stock):
    stock(product, loc.PIA, 1)
    with pytest.raises(BusinessRuleError) as exc:
        services.change_condition(product=product, location=loc.PIA, qty=1,
                                  from_condition="display", to_condition="new",
                                  user=staff.sales, reason="x")
    assert exc.value.code == "insufficient_stock"
    with pytest.raises(BusinessRuleError) as exc:
        services.change_condition(product=product, location=loc.PIA, qty=1,
                                  from_condition="new", to_condition="damaged",
                                  user=staff.sales, reason=" ")
    assert exc.value.code == "reason_required"


@pytest.mark.django_db
def test_condition_changes_cannot_be_edited(staff, loc, product, stock):
    stock(product, loc.PIA, 1)
    change = services.change_condition(product=product, location=loc.PIA, qty=1,
                                       from_condition="new", to_condition="display",
                                       user=staff.sales, reason="x")
    with pytest.raises(BusinessRuleError):
        change.save()
    with pytest.raises(BusinessRuleError):
        StockConditionChange.objects.all().delete()


@pytest.mark.django_db
def test_selling_a_display_piece_with_a_discount(staff, loc, stock):
    from apps.core.services import update_settings

    sofa = ProductFactory(code="EC-010", selling_price=Decimal("10000"))
    stock(sofa, loc.PIA, 2)
    services.change_condition(product=sofa, location=loc.PIA, qty=1, from_condition="new",
                              to_condition="display", user=staff.sales, reason="Sample")
    update_settings(user=staff.admin, max_salesperson_discount_pct=Decimal("20"))
    customer = CustomerFactory(type="walk_in", credit_allowed=True)

    order = sales.create_order(customer=customer, branch=loc.PIA, user=staff.sales, lines=[
        {"product": sofa, "qty": 1, "condition": "display", "discount": Decimal("2000")},
        {"product": sofa, "qty": 1}])
    order = sales.confirm_order(order=order, user=staff.sales)

    assert order.total_amount == Decimal("18000")
    assert counts(sofa, loc.PIA)["on_hand"] == 0
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_display_pieces_cannot_be_requested_from_the_warehouse(staff, loc, product):
    with pytest.raises(BusinessRuleError) as exc:
        sales.create_order(customer=CustomerFactory(), branch=loc.PIA, user=staff.sales,
                           lines=[{"product": product, "qty": 1, "condition": "display",
                                   "source_location": loc.PAW}])
    assert exc.value.code == "invalid_source"


@pytest.mark.django_db
def test_writing_off_damaged_pieces_needs_approval(staff, loc, product, stock):
    stock(product, loc.PAW, 5)
    services.change_condition(product=product, location=loc.PAW, qty=2,
                              from_condition="new", to_condition="damaged",
                              user=staff.store, reason="Broken legs")
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=-2,
                                             condition="damaged", reason="damage",
                                             user=staff.store, note="Beyond repair")
    assert counts(product, loc.PAW)["damaged"] == 2  # nothing moves until approved

    services.approve_adjustment(adjustment=adjustment, user=staff.accountant)

    assert counts(product, loc.PAW) == {"on_hand": 3, "new": 3, "display": 0, "damaged": 0,
                                        "available": 3}
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_damaged_piece_travels_to_pawlos_for_repair_and_comes_back_new(staff, loc, product,
                                                                      stock):
    stock(product, loc.PIA, 2)
    services.change_condition(product=product, location=loc.PIA, qty=1,
                              from_condition="new", to_condition="damaged",
                              user=staff.sales, reason="Torn seat")

    transfer = services.create_transfer(from_location=loc.PIA, to_location=loc.PAW,
                                        lines=[{"product": product, "qty": 1,
                                                "condition": "damaged"}], user=staff.admin)
    assert counts(product, loc.TRANSIT)["damaged"] == 1
    services.receive_transfer(transfer=transfer, user=staff.store)
    assert counts(product, loc.PAW)["damaged"] == 1

    services.change_condition(product=product, location=loc.PAW, qty=1,
                              from_condition="damaged", to_condition="new",
                              user=staff.store, reason="Repaired")
    assert counts(product, loc.PAW)["available"] == 1
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_a_broken_return_goes_into_the_damaged_count(staff, loc, product, stock):
    stock(product, loc.PIA, 2)
    order = sales.confirm_order(order=sales.create_order(
        customer=CustomerFactory(credit_allowed=True), branch=loc.PIA, user=staff.sales,
        lines=[{"product": product, "qty": 2}]), user=staff.sales)

    sales.return_goods(order=order, user=staff.accountant, location=loc.PIA, reason="Broken",
                       lines=[{"line_id": order.lines.get().pk, "qty": 1,
                               "condition": "damaged"}])

    assert counts(product, loc.PIA) == {"on_hand": 1, "new": 0, "display": 0, "damaged": 1,
                                        "available": 0}
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_low_stock_counts_only_sellable_stock(staff, loc, stock):
    chair = ProductFactory(code="LOW-2", min_stock=3)
    stock(chair, loc.PIA, 3)
    assert not low_stock_products().filter(pk=chair.pk).exists()

    services.change_condition(product=chair, location=loc.PIA, qty=1, from_condition="new",
                              to_condition="display", user=staff.sales, reason="Sample")

    assert low_stock_products().filter(pk=chair.pk).exists()


@pytest.mark.django_db
def test_rebuild_restores_tampered_display_counts(staff, loc, product, stock):
    stock(product, loc.PIA, 4)
    services.change_condition(product=product, location=loc.PIA, qty=2, from_condition="new",
                              to_condition="display", user=staff.sales, reason="Samples")
    StockBalance.objects.filter(product=product, location=loc.PIA).update(display=0)

    call_command("rebuild_stock_balances")

    assert counts(product, loc.PIA)["display"] == 2
    call_command("rebuild_stock_balances", "--check")


@pytest.mark.django_db
def test_api_condition_change_and_matrix(client_for, loc, product, stock):
    stock(product, loc.PIA, 4)
    client, _ = client_for("salesperson", home_location=loc.PIA)

    created = client.post("/api/v1/stock/condition-changes/", {
        "product": product.pk, "location": loc.PIA.pk, "qty": 1, "from_condition": "new",
        "to_condition": "display", "reason": "Window display"}, format="json")
    assert created.status_code == 201, created.data

    row = client.get("/api/v1/stock/summary/", {"search": product.code}).data["results"][0]
    assert row["stock"]["PIA"] == {"on_hand": 4, "reserved": 0, "display": 1, "damaged": 0,
                                   "available": 3}
    assert (row["total"], row["total_new"]) == (4, 3)


@pytest.mark.django_db
def test_random_condition_operations_keep_the_ledger_consistent(staff, loc):
    rng = random.Random(15)
    products = [ProductFactory(code=f"C-{i}") for i in range(2)]
    places = [loc.PIA, loc.DEN, loc.PAW]
    conditions = ["new", "display", "damaged"]
    ok = 0
    for _ in range(150):
        product, place, qty = rng.choice(products), rng.choice(places), rng.randint(1, 6)
        a, b = rng.sample(conditions, 2)
        kind = rng.choice(["receive", "change", "transfer", "adjust"])
        try:
            if kind == "receive":
                services.receive_goods(location=place, user=staff.admin,
                                       lines=[{"product": product, "qty": qty}])
            elif kind == "change":
                services.change_condition(product=product, location=place, qty=qty,
                                          from_condition=a, to_condition=b, user=staff.admin,
                                          reason="random")
            elif kind == "transfer":
                target = rng.choice([p for p in places if p != place])
                transfer = services.create_transfer(
                    from_location=place, to_location=target, user=staff.admin,
                    lines=[{"product": product, "qty": qty, "condition": a}])
                services.receive_transfer(transfer=transfer, user=staff.admin,
                                          received={transfer.lines.get().pk:
                                                    rng.randint(0, qty)})
            else:
                adjustment = services.propose_adjustment(
                    location=place, product=product, qty_delta=-qty, condition=a,
                    reason="count", user=staff.admin)
                services.approve_adjustment(adjustment=adjustment, user=staff.accountant)
            ok += 1
        except BusinessRuleError:
            pass
    assert ok > 50
    assert balance_mismatches() == []
