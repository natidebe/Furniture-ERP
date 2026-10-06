"""The only code that changes stock. Every change is a StockMovement plus a balance update
in the same transaction; corrections are reversals, never edits."""

import logging

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ERPPermission, Role
from apps.audit.services import audit_log
from apps.core.exceptions import BusinessRuleError
from apps.core.numbering import (
    ADJUSTMENT,
    CONDITION_CHANGE,
    GOODS_RECEIPT,
    MOVEMENT,
    TRANSFER,
    next_number,
)
from apps.notifications.services import notify

from .models import (
    TRANSIT_CODE,
    AdjustmentStatus,
    Condition,
    GoodsReceipt,
    GoodsReceiptLine,
    MovementType,
    StockAdjustment,
    StockBalance,
    StockConditionChange,
    StockMovement,
    StockTransfer,
    StockTransferLine,
    TransferStatus,
)
from .selectors import transit_location

logger = logging.getLogger(__name__)

# Movements tied to a document flow (requests, transfers, sales) are corrected through
# that flow, so the document and the stock stay in step. Only these can be reversed alone.
DIRECTLY_REVERSIBLE = {"goods_receipt"}


# ---------------------------------------------------------------- helpers

def _check_qty(qty) -> int:
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        raise BusinessRuleError("invalid_qty", "Quantity must be a positive whole number.")
    return qty


def _check_condition(condition) -> str:
    if condition not in Condition.values:
        raise BusinessRuleError("invalid_condition", "Choose new, display or damaged.")
    return condition


def check_lines(lines) -> list[dict]:
    """lines = [{"product": Product, "qty": int, "condition"?: str}, ...] — non-empty,
    one line per product and condition."""
    if not lines:
        raise BusinessRuleError("no_lines", "Add at least one product.")
    seen = set()
    for line in lines:
        _check_qty(line["qty"])
        key = (line["product"].pk, _check_condition(line.get("condition", Condition.NEW)))
        if key in seen:
            raise BusinessRuleError("duplicate_product",
                                    f"{line['product'].code} is listed twice.")
        seen.add(key)
    return lines


def _check_stock_location(location, *, allow_transit=False):
    if location.code == TRANSIT_CODE and not allow_transit:
        raise BusinessRuleError("transit_not_allowed", "In Transit cannot be used here.")
    if not location.is_active:
        raise BusinessRuleError("inactive_location", f"{location.code} is not active.")


def _is_admin(user) -> bool:
    return user.role == Role.ADMIN


def _require_own_location(user, location, action: str):
    """Storekeepers act only at their home location; accountants and admins anywhere."""
    if user.role in (Role.ACCOUNTANT, Role.ADMIN):
        return
    if user.role == Role.STOREKEEPER and user.home_location_id == location.pk:
        return
    raise BusinessRuleError("wrong_location", f"You cannot {action} at {location.code}.")


def _lock_balances(product, locations) -> dict:
    """Lock the balance rows for these locations, always in location-id order so two
    concurrent movements can never deadlock each other."""
    locations = sorted({loc.pk: loc for loc in locations if loc is not None}.values(),
                       key=lambda loc: loc.pk)
    # Create missing rows first without racing (a concurrent insert waits, then no-ops).
    StockBalance.objects.bulk_create(
        [StockBalance(product=product, location=loc) for loc in locations],
        ignore_conflicts=True,
    )
    balances = {}
    for loc in locations:
        balances[loc.pk] = StockBalance.objects.select_for_update().get(product=product,
                                                                       location=loc)
    return balances


def _queue_low_stock_check(product_id: int) -> None:
    """Runs after commit. A broker problem must never turn a saved movement into an error
    response (the user would retry and post it twice), so failures are only logged."""
    from .tasks import check_low_stock

    try:
        check_low_stock.apply_async(args=[product_id], retry=False)
    except Exception:  # logging is the whole point here
        logger.exception("Could not queue low-stock check for product %s", product_id)


# ---------------------------------------------------------------- core ledger

@transaction.atomic
def post_movement(*, product, qty, type, from_location=None, to_location=None,
                  reference_type, reference_id, person, customer=None, note="",
                  transaction_number="", reverses=None, consume_reservation=False,
                  condition=Condition.NEW) -> StockMovement:
    """Post one movement and update balances.

    consume_reservation=True takes stock that an open request reserved at from_location:
    on_hand and reserved both drop by qty. Otherwise only free new stock can leave, so stock
    held for one request can never be taken by another. `condition` display/damaged moves
    pieces out of / into those counts instead (D15); they are never reserved.
    """
    _check_qty(qty)
    _check_condition(condition)
    if consume_reservation and condition != Condition.NEW:
        raise BusinessRuleError("invalid_condition", "Only new stock is reserved.")
    if from_location is None and to_location is None:
        raise BusinessRuleError("no_location", "A movement needs a from or to location.")
    if from_location is not None and to_location is not None \
            and from_location.pk == to_location.pk:
        raise BusinessRuleError("same_location", "From and to must be different locations.")
    if to_location is not None and not to_location.is_active:
        raise BusinessRuleError("inactive_location", f"{to_location.code} is not active.")
    if consume_reservation and from_location is None:
        raise BusinessRuleError("no_location", "Reserved stock is taken from a location.")

    balances = _lock_balances(product, [from_location, to_location])

    if from_location is not None:
        src = balances[from_location.pk]
        if consume_reservation:
            if qty > src.reserved:
                raise BusinessRuleError(
                    "reservation_mismatch",
                    f"{product.code} at {from_location.code}: only {src.reserved} reserved.")
            src.reserved -= qty
        elif condition == Condition.NEW:
            if qty > src.available:
                raise BusinessRuleError(
                    "insufficient_stock",
                    f"Only {src.available} {product.code} available at {from_location.code}.")
        else:
            have = src.count_of(condition)
            if qty > have:
                raise BusinessRuleError(
                    "insufficient_stock",
                    f"Only {have} {condition} {product.code} at {from_location.code}.")
            setattr(src, condition, have - qty)
        src.on_hand -= qty
        src.save(update_fields=["on_hand", "reserved", "display", "damaged", "updated_at"])

    if to_location is not None:
        dst = balances[to_location.pk]
        dst.on_hand += qty
        if condition != Condition.NEW:
            setattr(dst, condition, dst.count_of(condition) + qty)
        dst.save(update_fields=["on_hand", "display", "damaged", "updated_at"])

    movement = StockMovement.objects.create(
        number=next_number(MOVEMENT), product=product, qty=qty, type=type,
        from_location=from_location, to_location=to_location,
        reference_type=reference_type, reference_id=str(reference_id),
        transaction_number=transaction_number, person=person, customer=customer,
        note=note, reverses=reverses, condition=condition)

    transaction.on_commit(lambda: _queue_low_stock_check(product.pk))
    return movement


@transaction.atomic
def change_condition(*, product, location, qty, from_condition, to_condition, user,
                     reason: str) -> StockConditionChange:
    """Put pieces on display, mark them damaged, or bring them back to new (D15). Staff at
    the location, accountants and admins. The location's total stays the same."""
    _check_qty(qty)
    _check_condition(from_condition)
    _check_condition(to_condition)
    if from_condition == to_condition:
        raise BusinessRuleError("invalid_condition", "Choose two different conditions.")
    reason = (reason or "").strip()
    if not reason:
        raise BusinessRuleError("reason_required", "Give a reason.")
    _check_stock_location(location)
    if not (user.role in (Role.ACCOUNTANT, Role.ADMIN)
            or user.home_location_id == location.pk):
        raise BusinessRuleError("wrong_location",
                                f"You cannot change stock condition at {location.code}.")

    bal = _lock_balances(product, [location])[location.pk]
    have = bal.available if from_condition == Condition.NEW else bal.count_of(from_condition)
    if qty > have:
        raise BusinessRuleError(
            "insufficient_stock",
            f"Only {have} {from_condition} {product.code} free at {location.code}.")
    if from_condition != Condition.NEW:
        setattr(bal, from_condition, bal.count_of(from_condition) - qty)
    if to_condition != Condition.NEW:
        setattr(bal, to_condition, bal.count_of(to_condition) + qty)
    bal.save(update_fields=["display", "damaged", "updated_at"])

    change = StockConditionChange.objects.create(
        number=next_number(CONDITION_CHANGE), product=product, location=location, qty=qty,
        from_condition=from_condition, to_condition=to_condition, reason=reason[:255],
        person=user)
    audit_log(actor=user, action="stock_condition_changed", obj=change, reason=reason,
              after={"product": product.code, "location": location.code, "qty": qty,
                     "from": from_condition, "to": to_condition})
    transaction.on_commit(lambda: _queue_low_stock_check(product.pk))
    return change


@transaction.atomic
def reserve(*, product, location, qty) -> StockBalance:
    _check_qty(qty)
    bal = _lock_balances(product, [location])[location.pk]
    if qty > bal.available:
        raise BusinessRuleError(
            "insufficient_stock",
            f"Only {bal.available} {product.code} free to reserve at {location.code}.")
    bal.reserved += qty
    bal.save(update_fields=["reserved", "updated_at"])
    return bal


@transaction.atomic
def unreserve(*, product, location, qty) -> StockBalance:
    _check_qty(qty)
    bal = _lock_balances(product, [location])[location.pk]
    if qty > bal.reserved:
        # Reservations must always match open requests; never paper over a mismatch.
        raise BusinessRuleError(
            "reservation_mismatch",
            f"{product.code} at {location.code}: only {bal.reserved} reserved, "
            f"cannot release {qty}.")
    bal.reserved -= qty
    bal.save(update_fields=["reserved", "updated_at"])
    return bal


@transaction.atomic
def reverse_movement(*, movement, person, reason: str, internal: bool = False) -> StockMovement:
    """Post the opposite movement. Needs `correct_transactions` (D5) and a reason.

    `internal=True` is for document flows (e.g. voiding a sale in Phase 3) that also fix
    their own document; the API only reverses DIRECTLY_REVERSIBLE movements.
    """
    if not person.has_erp_permission(ERPPermission.CORRECT_TRANSACTIONS):
        raise BusinessRuleError("permission_denied", "You are not allowed to correct stock.")
    reason = (reason or "").strip()
    if not reason:
        raise BusinessRuleError("reason_required", "Give a reason for the correction.")

    movement = StockMovement.objects.select_for_update().get(pk=movement.pk)
    if movement.type == MovementType.REVERSAL:
        raise BusinessRuleError("reverse_reversal", "A reversal cannot itself be reversed.")
    if StockMovement.objects.filter(reverses=movement).exists():
        raise BusinessRuleError("already_reversed", f"{movement.number} is already reversed.")
    if not internal and movement.reference_type not in DIRECTLY_REVERSIBLE:
        raise BusinessRuleError(
            "not_directly_reversible",
            f"{movement.number} belongs to {movement.reference_type} "
            f"{movement.reference_id}; correct it through that document.")

    reversal = post_movement(
        product=movement.product, qty=movement.qty, type=MovementType.REVERSAL,
        from_location=movement.to_location, to_location=movement.from_location,
        reference_type="reversal", reference_id=movement.number,
        transaction_number=movement.transaction_number, customer=movement.customer,
        person=person, note=reason[:255], reverses=movement, condition=movement.condition)
    audit_log(actor=person, action="movement_reversed", obj=movement, reason=reason,
              after={"reversal": reversal.number})
    return reversal


# ---------------------------------------------------------------- goods receipts

@transaction.atomic
def receive_goods(*, location, lines, user, reference="", note="",
                  received_at=None) -> GoodsReceipt:
    """Imported goods arrive (outside → location). One receipt movement per line."""
    _check_stock_location(location)
    _require_own_location(user, location, "receive goods")
    check_lines(lines)

    receipt = GoodsReceipt.objects.create(
        number=next_number(GOODS_RECEIPT), location=location, reference=reference,
        received_at=received_at or timezone.now(), received_by=user, note=note)
    for line in lines:
        GoodsReceiptLine.objects.create(receipt=receipt, product=line["product"],
                                        qty=line["qty"])
        post_movement(product=line["product"], qty=line["qty"], type=MovementType.RECEIPT,
                      to_location=location, reference_type="goods_receipt",
                      reference_id=receipt.number, transaction_number=receipt.number,
                      person=user, note=reference[:255])
    audit_log(actor=user, action="goods_received", obj=receipt,
              after={"location": location.code, "reference": reference,
                     "lines": {line["product"].code: line["qty"] for line in lines}})
    return receipt


# ---------------------------------------------------------------- adjustments

@transaction.atomic
def propose_adjustment(*, location, product, qty_delta: int, reason: str, user,
                       note="", condition=Condition.NEW) -> StockAdjustment:
    if not isinstance(qty_delta, int) or isinstance(qty_delta, bool) or qty_delta == 0:
        raise BusinessRuleError("invalid_qty", "The change must be a non-zero whole number.")
    _check_stock_location(location, allow_transit=True)
    if user.role == Role.SALESPERSON:
        raise BusinessRuleError("permission_denied", "Salespeople cannot adjust stock.")
    _require_own_location(user, location, "adjust stock")

    _check_condition(condition)
    adjustment = StockAdjustment.objects.create(
        number=next_number(ADJUSTMENT), location=location, product=product,
        qty_delta=qty_delta, reason=reason, note=note, proposed_by=user, condition=condition)
    audit_log(actor=user, action="adjustment_proposed", obj=adjustment,
              after={"location": location.code, "product": product.code,
                     "qty_delta": qty_delta, "reason": reason, "condition": condition},
              reason=note)
    notify("adjustment.proposed", adjustment)
    return adjustment


def _lock_proposed_adjustment(adjustment, user) -> StockAdjustment:
    if not user.has_erp_permission(ERPPermission.APPROVE_ADJUSTMENTS):
        raise BusinessRuleError("permission_denied", "You are not allowed to decide adjustments.")
    adjustment = StockAdjustment.objects.select_for_update().get(pk=adjustment.pk)
    if adjustment.status != AdjustmentStatus.PROPOSED:
        raise BusinessRuleError("invalid_state",
                                f"{adjustment.number} is already {adjustment.status}.")
    if adjustment.proposed_by_id == user.pk and not _is_admin(user):
        raise BusinessRuleError("own_adjustment",
                                "Someone else must approve an adjustment you proposed.")
    return adjustment


@transaction.atomic
def approve_adjustment(*, adjustment, user, note="") -> StockAdjustment:
    adjustment = _lock_proposed_adjustment(adjustment, user)
    qty = abs(adjustment.qty_delta)
    removing = adjustment.qty_delta < 0
    movement = post_movement(
        product=adjustment.product, qty=qty, type=MovementType.ADJUSTMENT,
        from_location=adjustment.location if removing else None,
        to_location=None if removing else adjustment.location,
        reference_type="adjustment", reference_id=adjustment.number,
        transaction_number=adjustment.number, person=user, condition=adjustment.condition,
        note=f"{adjustment.reason}: {adjustment.note}"[:255])
    adjustment.status = AdjustmentStatus.APPROVED
    adjustment.decided_by, adjustment.decided_at = user, timezone.now()
    adjustment.decision_note = note
    adjustment.movement = movement
    adjustment.save(update_fields=["status", "decided_by", "decided_at", "decision_note",
                                   "movement"])
    audit_log(actor=user, action="adjustment_approved", obj=adjustment, reason=note,
              after={"movement": movement.number, "qty_delta": adjustment.qty_delta})
    return adjustment


@transaction.atomic
def reject_adjustment(*, adjustment, user, note: str) -> StockAdjustment:
    if not (note or "").strip():
        raise BusinessRuleError("reason_required", "Give a reason for rejecting.")
    adjustment = _lock_proposed_adjustment(adjustment, user)
    adjustment.status = AdjustmentStatus.REJECTED
    adjustment.decided_by, adjustment.decided_at = user, timezone.now()
    adjustment.decision_note = note
    adjustment.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
    audit_log(actor=user, action="adjustment_rejected", obj=adjustment, reason=note)
    return adjustment


# ---------------------------------------------------------------- transfers

@transaction.atomic
def send_transfer(*, from_location, to_location, lines, user, stock_request=None,
                  transaction_number="", consume_reservation=False, note="") -> StockTransfer:
    """Move stock out to TRANSIT; it reaches to_location when receive_transfer runs.

    Internal: callers check who may send (create_transfer for manual transfers,
    requests.services.release_stock for request releases).
    """
    _check_stock_location(from_location)
    _check_stock_location(to_location)
    if from_location.pk == to_location.pk:
        raise BusinessRuleError("same_location", "From and to must be different locations.")
    check_lines(lines)
    transit = transit_location()

    number = next_number(TRANSFER)
    transfer = StockTransfer.objects.create(
        number=number, from_location=from_location, to_location=to_location,
        transaction_number=transaction_number or number, stock_request=stock_request,
        sent_by=user, note=note)
    for line in lines:
        condition = line.get("condition", Condition.NEW)
        StockTransferLine.objects.create(transfer=transfer, product=line["product"],
                                         qty_sent=line["qty"], condition=condition)
        post_movement(product=line["product"], qty=line["qty"],
                      type=MovementType.TRANSFER_OUT, from_location=from_location,
                      to_location=transit, reference_type="transfer", reference_id=number,
                      transaction_number=transfer.transaction_number, person=user,
                      consume_reservation=consume_reservation, condition=condition)
    notify("transfer.sent", transfer)
    return transfer


@transaction.atomic
def create_transfer(*, from_location, to_location, lines, user, note="") -> StockTransfer:
    """A manual transfer not tied to a request (admin / accountant only)."""
    if user.role not in (Role.ACCOUNTANT, Role.ADMIN):
        raise BusinessRuleError("permission_denied",
                                "Only accountants and admins send transfers without a request.")
    transfer = send_transfer(from_location=from_location, to_location=to_location,
                             lines=lines, user=user, note=note)
    audit_log(actor=user, action="transfer_sent", obj=transfer,
              after={"from": from_location.code, "to": to_location.code,
                     "lines": [f"{line['qty']} × {line['product'].code} "
                              f"({line.get('condition', Condition.NEW)})" for line in lines]})
    return transfer


@transaction.atomic
def receive_transfer(*, transfer, user, received=None) -> StockTransfer:
    """Book a transfer in at its destination.

    `received` = {line_id: qty}; lines left out are received in full. Units not received
    stay in TRANSIT and the transfer gets a discrepancy note for the accountant.
    """
    transfer = StockTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.status != TransferStatus.IN_TRANSIT:
        raise BusinessRuleError("invalid_state", f"{transfer.number} was already received.")
    if not (_is_admin(user) or user.home_location_id == transfer.to_location_id):
        raise BusinessRuleError("wrong_location",
                                f"Only staff at {transfer.to_location.code} can receive this.")

    received = dict(received or {})
    lines = list(transfer.lines.select_related("product"))
    unknown = set(received) - {line.pk for line in lines}
    if unknown:
        raise BusinessRuleError("unknown_line",
                                f"Lines {sorted(unknown)} are not on this transfer.")

    transit = transit_location()
    shortfalls = []
    for line in lines:
        qty = received.get(line.pk, line.qty_sent)
        if not isinstance(qty, int) or isinstance(qty, bool) or not 0 <= qty <= line.qty_sent:
            raise BusinessRuleError(
                "invalid_qty", f"{line.product.code}: receive between 0 and {line.qty_sent}.")
        if qty:
            post_movement(product=line.product, qty=qty, type=MovementType.TRANSFER_IN,
                          from_location=transit, to_location=transfer.to_location,
                          reference_type="transfer", reference_id=transfer.number,
                          transaction_number=transfer.transaction_number, person=user,
                          condition=line.condition)
        if qty < line.qty_sent:
            shortfalls.append(f"{line.product.code}: sent {line.qty_sent}, received {qty} "
                              f"({line.qty_sent - qty} still in transit)")
        line.qty_received = qty
        line.save(update_fields=["qty_received"])

    if transfer.stock_request_id:
        from apps.sales.services import on_transfer_received

        on_transfer_received(transfer=transfer,
                             received={line.pk: line.qty_received for line in lines})

    transfer.status = TransferStatus.RECEIVED
    transfer.received_by, transfer.received_at = user, timezone.now()
    transfer.discrepancy_note = "\n".join(shortfalls)
    transfer.save(update_fields=["status", "received_by", "received_at", "discrepancy_note"])
    if shortfalls:
        audit_log(actor=user, action="transfer_short_received", obj=transfer,
                  after={"shortfalls": shortfalls})
        notify("transfer.discrepancy", transfer)
    return transfer
