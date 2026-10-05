import threading

import pytest
from django.db import connection, transaction

from apps.core.exceptions import BusinessRuleError
from apps.inventory.models import MovementType, StockMovement, TransferStatus
from apps.inventory.services import receive_transfer
from apps.requests import services
from apps.requests.models import RequestStatus, StockRequest
from tests.factories import CustomerFactory, ProductFactory


def _request(staff, loc, product, qty, **kwargs):
    return services.create_stock_request(
        requesting_location=loc.PIA, source_location=loc.PAW,
        lines=[{"product": product, "qty": qty}], salesperson=staff.sales, **kwargs)


def _acknowledged(staff, loc, product, qty, **kwargs):
    request = _request(staff, loc, product, qty, **kwargs)
    return services.acknowledge_request(request=request, user=staff.store)


def _release(staff, request, qty, destination="branch"):
    line = request.lines.get()
    return services.release_stock(request=request, storekeeper=staff.store,
                                  destination_type=destination,
                                  lines=[{"line_id": line.pk, "qty": qty}])


# ---------------------------------------------------------------- creating

@pytest.mark.django_db
def test_request_reserves_stock_at_pawlos(staff, loc, product, stock, balance):
    stock(product, loc.PAW, 100)

    request = _request(staff, loc, product, 20, reference="ABC Furniture order")

    assert request.status == RequestStatus.PENDING
    assert request.number.startswith("SR-")
    assert request.transaction_number == request.number
    assert balance(product, loc.PAW) == (100, 20)


@pytest.mark.django_db
def test_request_cannot_reserve_more_than_free_stock(staff, loc, product, stock, balance):
    stock(product, loc.PAW, 10)
    _request(staff, loc, product, 8)

    with pytest.raises(BusinessRuleError) as exc:
        _request(staff, loc, product, 5)
    assert exc.value.code == "insufficient_stock"
    assert balance(product, loc.PAW) == (10, 8)


@pytest.mark.django_db
def test_salesperson_requests_only_for_own_branch(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    with pytest.raises(BusinessRuleError) as exc:
        services.create_stock_request(requesting_location=loc.DEN, source_location=loc.PAW,
                                      lines=[{"product": product, "qty": 1}],
                                      salesperson=staff.sales)
    assert exc.value.code == "wrong_location"


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["storekeeper", "accountant"])
def test_only_sales_staff_create_requests(staff, loc, product, stock, make_user, role):
    """The storekeeper who releases stock must never be the one who requested it."""
    stock(product, loc.PAW, 10)
    user = make_user(role=role, home_location=loc.PIA)
    with pytest.raises(BusinessRuleError) as exc:
        services.create_stock_request(requesting_location=loc.PIA, source_location=loc.PAW,
                                      lines=[{"product": product, "qty": 1}], salesperson=user)
    assert exc.value.code == "permission_denied"


@pytest.mark.django_db
def test_source_must_be_a_releasing_location(staff, loc, product, stock):
    stock(product, loc.DEN, 10)
    with pytest.raises(BusinessRuleError) as exc:
        services.create_stock_request(requesting_location=loc.PIA, source_location=loc.DEN,
                                      lines=[{"product": product, "qty": 1}],
                                      salesperson=staff.sales)
    assert exc.value.code == "invalid_location"


# ---------------------------------------------------------------- releasing

@pytest.mark.django_db
def test_no_release_before_acknowledge(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    request = _request(staff, loc, product, 5)

    with pytest.raises(BusinessRuleError) as exc:
        _release(staff, request, 5)
    assert exc.value.code == "invalid_state"


@pytest.mark.django_db
def test_partial_release_to_branch(staff, loc, product, stock, balance):
    stock(product, loc.PAW, 100)
    request = _acknowledged(staff, loc, product, 20)

    release = _release(staff, request, 15)

    request.refresh_from_db()
    assert request.status == RequestStatus.PARTIALLY_RELEASED
    assert request.lines.get().qty_released == 15
    assert balance(product, loc.PAW) == (85, 5)        # 5 still reserved for this request
    assert balance(product, loc.TRANSIT) == (15, 0)
    transfer = release.transfer
    assert transfer.status == TransferStatus.IN_TRANSIT
    assert (transfer.from_location, transfer.to_location) == (loc.PAW, loc.PIA)
    assert transfer.stock_request == request
    movements = StockMovement.objects.filter(type=MovementType.TRANSFER_OUT)
    assert {m.transaction_number for m in movements} == {request.transaction_number}


@pytest.mark.django_db
def test_full_release_then_branch_receives(staff, loc, product, stock, balance):
    stock(product, loc.PAW, 100)
    request = _acknowledged(staff, loc, product, 20)
    _release(staff, request, 15)
    release = _release(staff, request, 5)

    request.refresh_from_db()
    assert request.status == RequestStatus.RELEASED
    assert balance(product, loc.PAW) == (80, 0)

    for transfer in request.transfers.all():
        receive_transfer(transfer=transfer, user=staff.sales)
    assert balance(product, loc.PIA) == (20, 0)
    assert balance(product, loc.TRANSIT) == (0, 0)
    assert release.transaction_number == request.transaction_number


@pytest.mark.django_db
def test_customer_pickup_is_a_sale_to_the_customer(staff, loc, product, stock, balance):
    stock(product, loc.PAW, 10)
    customer = CustomerFactory(name="Jimma Furniture", type="out_of_city")
    request = _acknowledged(staff, loc, product, 4, customer=customer)

    _release(staff, request, 4, destination="customer_pickup")

    movement = StockMovement.objects.get(type=MovementType.SALE)
    assert (movement.from_location, movement.to_location) == (loc.PAW, None)
    assert movement.customer == customer
    assert movement.transaction_number == request.transaction_number
    assert balance(product, loc.PAW) == (6, 0)


@pytest.mark.django_db
def test_customer_pickup_needs_a_customer(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    request = _acknowledged(staff, loc, product, 4)

    with pytest.raises(BusinessRuleError) as exc:
        _release(staff, request, 4, destination="customer_pickup")
    assert exc.value.code == "customer_required"


@pytest.mark.django_db
@pytest.mark.parametrize("qty", [0, 6, -1])
def test_release_must_be_within_what_is_left(staff, loc, product, stock, qty):
    stock(product, loc.PAW, 10)
    request = _acknowledged(staff, loc, product, 5)

    with pytest.raises(BusinessRuleError) as exc:
        _release(staff, request, qty)
    assert exc.value.code == "qty_exceeds_request"


@pytest.mark.django_db
def test_storekeeper_of_another_location_cannot_release(staff, loc, product, stock,
                                                        make_user):
    stock(product, loc.PAW, 10)
    request = _acknowledged(staff, loc, product, 5)
    other = make_user(role="storekeeper", home_location=loc.DEN)

    with pytest.raises(BusinessRuleError) as exc:
        services.release_stock(request=request, storekeeper=other, destination_type="branch",
                               lines=[{"line_id": request.lines.get().pk, "qty": 5}])
    assert exc.value.code == "wrong_location"


@pytest.mark.django_db
def test_one_request_cannot_use_another_requests_reservation(staff, loc, product, stock,
                                                             balance):
    stock(product, loc.PAW, 10)
    first = _acknowledged(staff, loc, product, 4)
    second = _acknowledged(staff, loc, product, 6)

    _release(staff, first, 4)
    assert balance(product, loc.PAW) == (6, 6)  # all that is left belongs to the second
    _release(staff, second, 6)
    assert balance(product, loc.PAW) == (0, 0)


@pytest.mark.django_db
@pytest.mark.parametrize("closing", ["reject", "cancel", "released"])
def test_closed_requests_cannot_be_released(staff, loc, product, stock, closing):
    stock(product, loc.PAW, 10)
    request = _acknowledged(staff, loc, product, 5)
    if closing == "reject":
        services.reject_request(request=request, user=staff.store, reason="No stock")
    elif closing == "cancel":
        services.cancel_request(request=request, user=staff.sales, reason="Customer left")
    else:
        _release(staff, request, 5)
    request.refresh_from_db()

    with pytest.raises(BusinessRuleError) as exc:
        _release(staff, request, 1)
    assert exc.value.code in ("invalid_state", "qty_exceeds_request")


# ---------------------------------------------------------------- reject / cancel / close

@pytest.mark.django_db
def test_reject_frees_the_reservation(staff, loc, product, stock, balance):
    stock(product, loc.PAW, 10)
    request = _request(staff, loc, product, 7)

    services.reject_request(request=request, user=staff.store, reason="Damaged stock")

    request.refresh_from_db()
    assert request.status == RequestStatus.REJECTED
    assert request.close_reason == "Damaged stock"
    assert balance(product, loc.PAW) == (10, 0)


@pytest.mark.django_db
def test_only_requester_or_admin_cancel(staff, loc, product, stock, make_user):
    stock(product, loc.PAW, 10)
    request = _request(staff, loc, product, 2)
    other_sales = make_user(role="salesperson", home_location=loc.PIA)

    with pytest.raises(BusinessRuleError) as exc:
        services.cancel_request(request=request, user=other_sales, reason="x")
    assert exc.value.code == "permission_denied"
    services.cancel_request(request=request, user=staff.admin, reason="x")


@pytest.mark.django_db
def test_cancel_after_a_release_is_refused_close_frees_the_rest(staff, loc, product, stock,
                                                               balance):
    stock(product, loc.PAW, 10)
    request = _acknowledged(staff, loc, product, 8)
    _release(staff, request, 3)

    with pytest.raises(BusinessRuleError) as exc:
        services.cancel_request(request=request, user=staff.sales, reason="x")
    assert exc.value.code == "invalid_state"

    services.close_request(request=request, user=staff.sales, reason="Customer took 3 only")
    request.refresh_from_db()
    assert request.status == RequestStatus.CLOSED
    assert balance(product, loc.PAW) == (7, 0)


@pytest.mark.django_db
def test_reasons_are_required(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    request = _request(staff, loc, product, 2)
    for action in (services.reject_request, services.cancel_request):
        with pytest.raises(BusinessRuleError) as exc:
            action(request=request, user=staff.admin, reason=" ")
        assert exc.value.code == "reason_required"


# ---------------------------------------------------------------- concurrency

@pytest.mark.skipif(connection.vendor != "postgresql", reason="needs Postgres row locks")
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_two_storekeepers_releasing_the_last_units_at_once(staff, loc, stock):
    """Two concurrent releases of the same 5 units: exactly one succeeds."""
    product = ProductFactory(code="LAST-5")
    stock(product, loc.PAW, 5)
    request = _acknowledged(staff, loc, product, 5)
    line_id = request.lines.get().pk
    results, barrier = [], threading.Barrier(2)

    def worker():
        try:
            barrier.wait()
            with transaction.atomic():
                services.release_stock(request=StockRequest.objects.get(pk=request.pk),
                                       storekeeper=staff.store, destination_type="branch",
                                       lines=[{"line_id": line_id, "qty": 5}])
            results.append("ok")
        except BusinessRuleError as exc:
            results.append(exc.code)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == ["invalid_state", "ok"]
    assert StockMovement.objects.filter(type=MovementType.TRANSFER_OUT).count() == 1
