import random

import pytest
from django.core.management import CommandError, call_command

from apps.audit.models import AuditLog
from apps.core.exceptions import BusinessRuleError
from apps.inventory import services
from apps.inventory.models import StockBalance, StockTransfer, TransferStatus
from apps.inventory.selectors import balance_mismatches
from apps.requests import services as requests
from apps.requests.models import OPEN_STATUSES, StockRequest
from tests.factories import CustomerFactory, ProductFactory


@pytest.mark.django_db
def test_check_passes_on_a_clean_ledger(loc, product, stock):
    stock(product, loc.PAW, 10)

    call_command("rebuild_stock_balances", "--check")


@pytest.mark.django_db
def test_check_reports_and_rebuild_fixes_a_tampered_balance(loc, product, stock, balance):
    stock(product, loc.PAW, 10)
    StockBalance.objects.filter(product=product).update(on_hand=12)

    with pytest.raises(CommandError):
        call_command("rebuild_stock_balances", "--check")
    assert balance(product, loc.PAW) == (12, 0)  # --check changes nothing

    call_command("rebuild_stock_balances")

    assert balance(product, loc.PAW) == (10, 0)
    assert AuditLog.objects.filter(action="stock_balance_rebuilt").count() == 1
    call_command("rebuild_stock_balances", "--check")


@pytest.mark.django_db
def test_check_catches_a_reservation_leak(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    requests.create_stock_request(requesting_location=loc.PIA, source_location=loc.PAW,
                                  lines=[{"product": product, "qty": 4}], salesperson=staff.sales)
    StockBalance.objects.filter(product=product).update(reserved=1)

    mismatches = balance_mismatches()

    assert len(mismatches) == 1
    assert (mismatches[0]["reserved"], mismatches[0]["expected_reserved"]) == (1, 4)


@pytest.mark.django_db
def test_random_operations_keep_balances_equal_to_the_ledger(staff, loc):
    """Property test (BUILD_PHASES 2.5): 200 random operations, then the ledger check."""
    rng = random.Random(20261005)
    products = [ProductFactory(code=f"P-{i}") for i in range(3)]
    customer = CustomerFactory()
    shops = [loc.PIA, loc.DEN]
    done = {"ok": 0, "refused": 0}

    def attempt(operation, **kwargs):
        try:
            operation(**kwargs)
            done["ok"] += 1
        except BusinessRuleError:
            done["refused"] += 1  # refusals are fine; they must leave no trace

    for _ in range(200):
        product = rng.choice(products)
        qty = rng.randint(1, 15)
        kind = rng.choice(["receive", "request", "acknowledge", "release", "receive_transfer",
                           "cancel", "close", "transfer", "adjust"])
        if kind == "receive":
            attempt(services.receive_goods, location=rng.choice([loc.PAW, *shops]),
                    lines=[{"product": product, "qty": qty}], user=staff.admin)
        elif kind == "request":
            attempt(requests.create_stock_request, requesting_location=loc.PIA,
                    source_location=loc.PAW, lines=[{"product": product, "qty": qty}],
                    salesperson=staff.sales,
                    customer=customer if rng.random() < 0.5 else None)
        elif kind == "acknowledge":
            pending = StockRequest.objects.filter(status="pending").first()
            if pending:
                attempt(requests.acknowledge_request, request=pending, user=staff.store)
        elif kind == "release":
            open_request = StockRequest.objects.filter(
                status__in=["acknowledged", "partially_released"]).order_by("?").first()
            if open_request:
                line = open_request.lines.first()
                attempt(requests.release_stock, request=open_request, storekeeper=staff.store,
                        destination_type=("customer_pickup" if open_request.customer_id
                                          else "branch"),
                        lines=[{"line_id": line.pk,
                                "qty": rng.randint(1, max(1, line.qty_remaining))}])
        elif kind == "receive_transfer":
            transfer = StockTransfer.objects.filter(status=TransferStatus.IN_TRANSIT).first()
            if transfer:
                line = transfer.lines.first()
                attempt(services.receive_transfer, transfer=transfer, user=staff.admin,
                        received={line.pk: rng.randint(0, line.qty_sent)})
        elif kind == "cancel":
            request = StockRequest.objects.filter(status__in=["pending", "acknowledged"]).first()
            if request:
                attempt(requests.cancel_request, request=request, user=staff.sales,
                        reason="random")
        elif kind == "close":
            request = StockRequest.objects.filter(status="partially_released").first()
            if request:
                attempt(requests.close_request, request=request, user=staff.store,
                        reason="random")
        elif kind == "transfer":
            attempt(services.create_transfer, from_location=loc.PAW,
                    to_location=rng.choice(shops), lines=[{"product": product, "qty": qty}],
                    user=staff.admin)
        else:
            adjustment = services.propose_adjustment(
                location=rng.choice([loc.PAW, *shops]), product=product,
                qty_delta=rng.choice([-1, 1]) * qty, reason="count", user=staff.admin)
            attempt(services.approve_adjustment, adjustment=adjustment, user=staff.accountant)

        # Invariants hold after every single step, not only at the end.
        assert not StockBalance.objects.filter(on_hand__lt=0).exists()

    assert done["ok"] > 50, done  # the run exercised real work, not only refusals
    assert balance_mismatches() == []
    call_command("rebuild_stock_balances", "--check")
    for request in StockRequest.objects.filter(status__in=OPEN_STATUSES):
        for line in request.lines.all():
            assert 0 <= line.qty_released <= line.qty_requested
