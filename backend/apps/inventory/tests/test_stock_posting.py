import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import ERPPermission
from apps.accounts.services import set_erp_permissions
from apps.audit.models import AuditLog
from apps.core.exceptions import BusinessRuleError
from apps.inventory import services
from apps.inventory.models import MovementType, StockBalance, StockMovement


@pytest.mark.django_db
def test_goods_receipt_adds_stock_with_one_movement_per_line(staff, loc, product, balance):
    receipt = services.receive_goods(location=loc.PAW, lines=[{"product": product, "qty": 100}],
                                     user=staff.store, reference="Container 7")

    assert balance(product, loc.PAW) == (100, 0)
    movement = StockMovement.objects.get()
    assert movement.type == MovementType.RECEIPT
    assert (movement.from_location, movement.to_location) == (None, loc.PAW)
    assert movement.reference_id == receipt.number == movement.transaction_number
    assert movement.person == staff.store
    assert receipt.number.startswith("GR-")


@pytest.mark.django_db
def test_storekeeper_receives_only_at_own_location(staff, loc, product):
    with pytest.raises(BusinessRuleError) as exc:
        services.receive_goods(location=loc.PIA, lines=[{"product": product, "qty": 1}],
                               user=staff.store)
    assert exc.value.code == "wrong_location"


@pytest.mark.django_db
def test_goods_cannot_be_received_into_transit(staff, loc, product):
    with pytest.raises(BusinessRuleError) as exc:
        services.receive_goods(location=loc.TRANSIT, lines=[{"product": product, "qty": 1}],
                               user=staff.admin)
    assert exc.value.code == "transit_not_allowed"


@pytest.mark.django_db
@pytest.mark.parametrize("qty", [0, -3, 2.5, True, "4"])
def test_quantity_must_be_a_positive_whole_number(staff, loc, product, qty):
    with pytest.raises(BusinessRuleError) as exc:
        services.receive_goods(location=loc.PAW, lines=[{"product": product, "qty": qty}],
                               user=staff.admin)
    assert exc.value.code == "invalid_qty"


@pytest.mark.django_db
def test_same_product_twice_is_refused(staff, loc, product):
    with pytest.raises(BusinessRuleError) as exc:
        services.receive_goods(location=loc.PAW, user=staff.admin,
                               lines=[{"product": product, "qty": 1},
                                      {"product": product, "qty": 2}])
    assert exc.value.code == "duplicate_product"


@pytest.mark.django_db
def test_taking_more_than_available_fails_and_changes_nothing(staff, loc, product, stock,
                                                              balance):
    stock(product, loc.PIA, 3)
    count = StockMovement.objects.count()

    with pytest.raises(BusinessRuleError) as exc:
        services.post_movement(product=product, qty=4, type=MovementType.SALE,
                               from_location=loc.PIA, reference_type="test", reference_id="1",
                               person=staff.sales)

    assert exc.value.code == "insufficient_stock"
    assert balance(product, loc.PIA) == (3, 0)
    assert StockMovement.objects.count() == count


@pytest.mark.django_db
def test_reserved_stock_cannot_be_taken_as_free_stock(staff, loc, product, stock, balance):
    stock(product, loc.PAW, 10)
    services.reserve(product=product, location=loc.PAW, qty=8)

    with pytest.raises(BusinessRuleError) as exc:
        services.post_movement(product=product, qty=3, type=MovementType.SALE,
                               from_location=loc.PAW, reference_type="test", reference_id="1",
                               person=staff.store)

    assert exc.value.code == "insufficient_stock"
    assert balance(product, loc.PAW) == (10, 8)


@pytest.mark.django_db
def test_consuming_a_reservation_cannot_take_more_than_reserved(staff, loc, product, stock):
    """The Phase 2 fix: a release uses only its own reservation, never someone else's."""
    stock(product, loc.PAW, 10)
    services.reserve(product=product, location=loc.PAW, qty=2)

    with pytest.raises(BusinessRuleError) as exc:
        services.post_movement(product=product, qty=5, type=MovementType.SALE,
                               from_location=loc.PAW, reference_type="test", reference_id="1",
                               person=staff.store, consume_reservation=True)
    assert exc.value.code == "reservation_mismatch"


@pytest.mark.django_db
def test_unreserving_more_than_reserved_is_an_error_not_a_silent_zero(loc, product, stock):
    stock(product, loc.PAW, 10)
    services.reserve(product=product, location=loc.PAW, qty=2)

    with pytest.raises(BusinessRuleError) as exc:
        services.unreserve(product=product, location=loc.PAW, qty=3)
    assert exc.value.code == "reservation_mismatch"


@pytest.mark.django_db
def test_database_refuses_negative_or_over_reserved_balances(loc, product, stock):
    stock(product, loc.PAW, 5)

    with pytest.raises(IntegrityError), transaction.atomic():
        StockBalance.objects.filter(product=product).update(on_hand=-1)
    with pytest.raises(IntegrityError), transaction.atomic():
        StockBalance.objects.filter(product=product).update(reserved=6)


@pytest.mark.django_db
def test_movements_are_immutable(loc, product, stock):
    stock(product, loc.PAW, 5)
    movement = StockMovement.objects.get()

    with pytest.raises(BusinessRuleError):
        movement.save()
    with pytest.raises(BusinessRuleError):
        movement.delete()
    with pytest.raises(BusinessRuleError):
        StockMovement.objects.filter(pk=movement.pk).update(qty=1)
    with pytest.raises(BusinessRuleError):
        StockMovement.objects.all().delete()


@pytest.mark.django_db
def test_movement_numbers_are_sequential(loc, product, stock):
    stock(product, loc.PAW, 1)
    stock(product, loc.PAW, 1)

    numbers = list(StockMovement.objects.order_by("id").values_list("number", flat=True))
    assert [n[-5:] for n in numbers] == ["00001", "00002"]


# ---------------------------------------------------------------- reversals

def _grant_correct(user):
    set_erp_permissions(user, [ERPPermission.CORRECT_TRANSACTIONS])


@pytest.mark.django_db
def test_reversing_a_receipt_restores_balance_and_is_audited(staff, loc, product, stock,
                                                             balance):
    stock(product, loc.PAW, 10)
    movement = StockMovement.objects.get()

    reversal = services.reverse_movement(movement=movement, person=staff.admin,
                                         reason="Wrong product received")

    assert balance(product, loc.PAW) == (0, 0)
    assert reversal.type == MovementType.REVERSAL
    assert reversal.reverses == movement
    assert reversal.transaction_number == movement.transaction_number
    assert AuditLog.objects.filter(action="movement_reversed", object_id=str(movement.pk),
                                   reason="Wrong product received").exists()


@pytest.mark.django_db
def test_a_movement_can_be_reversed_only_once(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    movement = StockMovement.objects.get()
    reversal = services.reverse_movement(movement=movement, person=staff.admin, reason="x")

    with pytest.raises(BusinessRuleError) as exc:
        services.reverse_movement(movement=movement, person=staff.admin, reason="x")
    assert exc.value.code == "already_reversed"
    with pytest.raises(BusinessRuleError) as exc:
        services.reverse_movement(movement=reversal, person=staff.admin, reason="x")
    assert exc.value.code == "reverse_reversal"


@pytest.mark.django_db
def test_reversal_needs_correct_transactions(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    movement = StockMovement.objects.get()

    with pytest.raises(BusinessRuleError) as exc:
        services.reverse_movement(movement=movement, person=staff.accountant, reason="x")
    assert exc.value.code == "permission_denied"

    _grant_correct(staff.accountant)
    services.reverse_movement(movement=movement, person=staff.accountant, reason="x")


@pytest.mark.django_db
def test_reversal_needs_a_reason(staff, loc, product, stock):
    stock(product, loc.PAW, 10)

    with pytest.raises(BusinessRuleError) as exc:
        services.reverse_movement(movement=StockMovement.objects.get(), person=staff.admin,
                                  reason="  ")
    assert exc.value.code == "reason_required"


@pytest.mark.django_db
def test_document_movements_are_corrected_through_their_document(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    transfer = services.create_transfer(from_location=loc.PAW, to_location=loc.PIA,
                                        lines=[{"product": product, "qty": 2}], user=staff.admin)
    movement = StockMovement.objects.get(reference_id=transfer.number)

    with pytest.raises(BusinessRuleError) as exc:
        services.reverse_movement(movement=movement, person=staff.admin, reason="x")
    assert exc.value.code == "not_directly_reversible"


@pytest.mark.django_db
def test_reversing_a_receipt_cannot_take_reserved_stock(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    services.reserve(product=product, location=loc.PAW, qty=5)

    with pytest.raises(BusinessRuleError) as exc:
        services.reverse_movement(movement=StockMovement.objects.get(), person=staff.admin,
                                  reason="x")
    assert exc.value.code == "insufficient_stock"
