"""Sales orders: from entry to handover (BUILD_PHASES.md 3.2).

Goods reach the customer in one of three ways, each recorded as a `sale` movement and a
delivery note, all carrying the order number as the transaction number (D4):

1. From the branch's own stock when the sale is confirmed.
2. From Pawlos to the branch: a stock request + transfer; on arrival the goods are held
   (reserved) at the branch for this sale, then handed over with release_from_branch.
3. Customer pickup at Pawlos: the storekeeper's release sells straight to the customer.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounts.models import ERPPermission, Role
from apps.audit.services import audit_log
from apps.catalog.selectors import price_for
from apps.core.exceptions import BusinessRuleError
from apps.core.numbering import DELIVERY_NOTE, SALES_ORDER, SALES_RETURN, next_number
from apps.core.services import get_settings
from apps.inventory import services as inventory
from apps.inventory.models import (
    TRANSIT_CODE,
    Condition,
    MovementType,
    StockMovement,
    TransferStatus,
)
from apps.notifications.services import notify
from apps.payments import selectors as money
from apps.payments import services as payments

from .models import (
    BILLABLE_STATUSES,
    EDITABLE_STATUSES,
    Channel,
    DeliveryNote,
    DeliveryNoteLine,
    FulfillmentStatus,
    ReceiptType,
    SalesOrder,
    SalesOrderLine,
    SalesReturn,
    SalesReturnLine,
)

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


# ---------------------------------------------------------------- helpers

def _lock(order) -> SalesOrder:
    return SalesOrder.objects.select_for_update(of=("self",)).select_related(
        "customer", "branch", "salesperson").get(pk=order.pk)


def _require_reason(reason: str) -> str:
    reason = (reason or "").strip()
    if not reason:
        raise BusinessRuleError("reason_required", "Give a reason.")
    return reason


def _require_order_staff(user, order, action: str):
    """The order's own salesperson, or an accountant or admin."""
    if user.role in (Role.ACCOUNTANT, Role.ADMIN):
        return
    if user.role == Role.SALESPERSON and order.salesperson_id == user.pk:
        return
    raise BusinessRuleError("permission_denied", f"You cannot {action} this sale.")


def direct_locations(branch) -> list:
    """Where a branch sells from directly: itself and its active sub-stores (Underground)."""
    return [branch, *branch.children.filter(is_active=True, can_sell=True)]


def _qty(value) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise BusinessRuleError("invalid_qty", "Quantity must be a positive whole number.")
    return value


def _discount_limit_ok(user, discount: Decimal, gross: Decimal) -> bool:
    if discount == 0 or user.has_erp_permission(ERPPermission.APPROVE_DISCOUNTS):
        return True
    limit = get_settings().max_salesperson_discount_pct
    return discount * HUNDRED <= limit * gross


def _build_lines(order, lines, user):
    """lines = [{"product", "qty", "discount"?, "source_location"?, "condition"?}] →
    SalesOrderLine rows. Prices come from the product for this customer (D11), never from the
    request. Display and damaged pieces (D15) are sold from the branch's own stock, usually
    with a discount."""
    if not lines:
        raise BusinessRuleError("no_lines", "Add at least one product.")
    direct = {loc.pk for loc in direct_locations(order.branch)}
    seen = set()
    for item in lines:
        product = item["product"]
        condition = item.get("condition") or Condition.NEW
        if condition not in Condition.values:
            raise BusinessRuleError("invalid_condition", "Choose new, display or damaged.")
        if (product.pk, condition) in seen:
            raise BusinessRuleError("duplicate_product", f"{product.code} is listed twice.")
        seen.add((product.pk, condition))
        if not product.is_active:
            raise BusinessRuleError("inactive_product", f"{product.code} is not sold any more.")
        qty = _qty(item["qty"])
        source = item.get("source_location") or order.branch
        if source.code == TRANSIT_CODE or not source.is_active or not (
                source.pk in direct or source.can_release):
            raise BusinessRuleError("invalid_source",
                                    f"{product.code} cannot come from {source.code}.")
        if condition != Condition.NEW and source.pk not in direct:
            raise BusinessRuleError("invalid_source",
                                    f"A {condition} {product.code} is sold from the branch's "
                                    f"own stock, not requested from {source.code}.")
        unit_price = price_for(product, order.customer)
        gross = unit_price * qty
        discount = Decimal(str(item.get("discount") or 0)).quantize(CENT, ROUND_HALF_UP)
        if discount < 0 or discount > gross:
            raise BusinessRuleError("invalid_discount",
                                    f"{product.code}: discount must be between 0 and {gross}.")
        if not _discount_limit_ok(user, discount, gross):
            raise BusinessRuleError(
                "discount_needs_approval",
                f"{product.code}: a {discount * HUNDRED / gross:.1f}% discount is above the "
                f"{get_settings().max_salesperson_discount_pct}% limit; ask the accountant.")
        SalesOrderLine.objects.create(order=order, product=product, qty=qty,
                                      unit_price=unit_price, discount=discount,
                                      line_total=gross - discount, source_location=source,
                                      condition=condition)


def recompute_total(order) -> SalesOrder:
    lines = order.lines.aggregate(t=Sum("line_total"))["t"] or Decimal("0")
    returned = order.returns.aggregate(t=Sum("amount"))["t"] or Decimal("0")
    order.total_amount = (lines - returned).quantize(CENT)
    order.save(update_fields=["total_amount", "updated_at"])
    return order


def _refresh_fulfillment(order) -> SalesOrder:
    if order.fulfillment_status not in BILLABLE_STATUSES:
        return order
    lines = list(order.lines.all())
    if all(line.qty_released == line.qty for line in lines):
        status = FulfillmentStatus.RELEASED
    elif any(line.qty_released for line in lines):
        status = FulfillmentStatus.PARTIALLY_RELEASED
    else:
        return order  # still confirmed / prepared
    if order.fulfillment_status != status:
        order.fulfillment_status = status
        order.save(update_fields=["fulfillment_status", "updated_at"])
        if status == FulfillmentStatus.RELEASED:
            notify("order.released", order)
    return order


def _hand_over(order, location, items, user, *, consume_reservation=False) -> DeliveryNote:
    """Sell `items` = [(order_line, qty)] from `location` to the customer: one delivery note,
    one sale movement per line."""
    note = DeliveryNote.objects.create(number=next_number(DELIVERY_NOTE), order=order,
                                       location=location, issued_by=user)
    for line, qty in items:
        DeliveryNoteLine.objects.create(note=note, order_line=line, product=line.product,
                                        qty=qty)
        inventory.post_movement(
            product=line.product, qty=qty, type=MovementType.SALE, from_location=location,
            customer=order.customer, reference_type="delivery_note", reference_id=note.number,
            transaction_number=order.number, person=user,
            consume_reservation=consume_reservation, condition=line.condition)
        line.qty_released += qty
        line.save(update_fields=["qty_released"])
    return note


def _pipeline(order, line) -> int:
    """Units of this line already on their way: open request quantities + goods in transit."""
    from apps.inventory.models import StockTransferLine
    from apps.requests.models import OPEN_STATUSES, StockRequestLine

    requested = (StockRequestLine.objects
                 .filter(request__order=order, request__status__in=OPEN_STATUSES,
                         product=line.product)
                 .aggregate(t=Sum("qty_requested") - Sum("qty_released"))["t"] or 0)
    in_transit = (StockTransferLine.objects
                  .filter(transfer__stock_request__order=order, product=line.product,
                          transfer__status=TransferStatus.IN_TRANSIT)
                  .aggregate(t=Sum("qty_sent"))["t"] or 0)
    return requested + in_transit


def still_needed(order, line) -> int:
    """Units of a warehouse-sourced line that nothing is yet bringing to the customer."""
    return max(0, line.qty_open - line.qty_awaiting - _pipeline(order, line))


def _check_credit(order, user):
    """A sale left partly unpaid needs credit: the customer must be allowed credit and stay
    within their limit — unless the user has approve_credit (Q11)."""
    from apps.customers.selectors import customer_balance

    unpaid = money.order_remaining(order)
    if unpaid <= 0 or user.has_erp_permission(ERPPermission.APPROVE_CREDIT):
        return
    customer = order.customer
    if not customer.credit_allowed:
        raise BusinessRuleError(
            "credit_not_allowed",
            f"{customer.name} does not buy on credit: {unpaid} is unpaid. Take the payment "
            f"first, or ask the accountant to approve.")
    if customer.credit_limit is not None:
        owed_after = customer_balance(customer)["outstanding"] + unpaid
        if owed_after > customer.credit_limit:
            raise BusinessRuleError(
                "credit_limit_exceeded",
                f"{customer.name} would owe {owed_after}, above their limit of "
                f"{customer.credit_limit}. Ask the accountant to approve.")


def _close_open_requests(order, user, reason):
    from apps.requests.models import OPEN_STATUSES
    from apps.requests.services import close_for_order

    for request in order.stock_requests.filter(status__in=OPEN_STATUSES):
        close_for_order(request=request, user=user, reason=reason)


def _free_awaiting(order):
    for line in order.lines.select_for_update().filter(qty_awaiting__gt=0):
        inventory.unreserve(product=line.product, location=order.branch, qty=line.qty_awaiting)
        line.qty_awaiting = 0
        line.save(update_fields=["qty_awaiting"])


# ---------------------------------------------------------------- create / edit

@transaction.atomic
def create_order(*, customer, branch, lines, user, channel=Channel.WALK_IN,
                 receipt_type=ReceiptType.NONE, notes="", payment=None, replaces=None,
                 salesperson=None) -> SalesOrder:
    """Create a draft (walk-in) or pending (phone) sale. `payment` = the fields of
    payments.services.record_payment except customer/allocations; it is allocated to this
    order in the same transaction."""
    if user.role == Role.SALESPERSON:
        if branch.pk != user.home_location_id:
            raise BusinessRuleError("wrong_location", "You can only sell at your own branch.")
        salesperson = user
    elif user.role not in (Role.ACCOUNTANT, Role.ADMIN):
        raise BusinessRuleError("permission_denied", "Only sales staff create sales.")
    if branch.code == TRANSIT_CODE or not branch.is_active or not branch.can_sell:
        raise BusinessRuleError("invalid_location", f"{branch.code} does not sell.")
    if not customer.is_active:
        raise BusinessRuleError("inactive_customer", f"{customer.name} is not active.")
    if channel not in Channel.values or receipt_type not in ReceiptType.values:
        raise BusinessRuleError("invalid_choice", "Choose a valid channel and receipt type.")
    if replaces is not None:
        replaces = SalesOrder.objects.select_for_update().get(pk=replaces.pk)
        if replaces.fulfillment_status != FulfillmentStatus.VOIDED:
            raise BusinessRuleError("invalid_state", "Only a voided sale can be re-issued.")
        if SalesOrder.objects.filter(replaces=replaces).exists():
            raise BusinessRuleError("already_replaced",
                                    f"{replaces.number} was already re-issued.")

    order = SalesOrder.objects.create(
        number=next_number(SALES_ORDER), customer=customer, branch=branch,
        salesperson=salesperson or user, channel=channel, receipt_type=receipt_type,
        notes=notes, replaces=replaces, created_by=user,
        fulfillment_status=(FulfillmentStatus.PENDING if channel == Channel.PHONE
                            else FulfillmentStatus.DRAFT))
    _build_lines(order, lines, user)
    recompute_total(order)
    if payment:
        payments.record_payment(customer=customer, recorded_by=user,
                                allocations=[{"order": order, "amount": payment["amount"]}],
                                **payment)
    payments.refresh_payment_status(order)
    audit_log(actor=user, action="order_created", obj=order,
              after={"total": str(order.total_amount), "customer": customer.name,
                     "replaces": replaces.number if replaces else None})
    return order


@transaction.atomic
def update_draft_order(*, order, user, lines=None, customer=None, receipt_type=None,
                       notes=None) -> SalesOrder:
    """Edit a sale before confirmation. Changing the customer re-prices the lines (D11)."""
    order = _lock(order)
    _require_order_staff(user, order, "edit")
    if order.fulfillment_status not in EDITABLE_STATUSES:
        raise BusinessRuleError("invalid_state", f"{order.number} is already confirmed.")
    has_payments = money.active_allocations().filter(order=order).exists()
    if receipt_type is not None and receipt_type != order.receipt_type and has_payments:
        raise BusinessRuleError("has_payments",
                                "Payments are recorded on this sale; the receipt type is fixed.")
    if customer is not None and customer.pk != order.customer_id:
        if has_payments:
            raise BusinessRuleError("has_payments",
                                    "Payments are recorded on this sale; the customer is fixed.")
        order.customer = customer
        if lines is None:  # re-price the same lines for the new customer
            lines = [{"product": ln.product, "qty": ln.qty, "discount": ln.discount,
                      "source_location": ln.source_location, "condition": ln.condition}
                     for ln in order.lines.all()]
    if receipt_type is not None:
        order.receipt_type = receipt_type
    if notes is not None:
        order.notes = notes
    order.save()
    if lines is not None:
        from apps.payments.models import PaymentAllocation

        if PaymentAllocation.objects.filter(order_line__order=order).exists():
            raise BusinessRuleError("has_payments",
                                    "Payments were made for specific lines; the lines are fixed.")
        order.lines.all().delete()
        _build_lines(order, lines, user)
    recompute_total(order)
    if order.total_amount < money.order_paid(order):
        raise BusinessRuleError("below_paid", "The new total is below what is already paid.")
    payments.refresh_payment_status(order)
    audit_log(actor=user, action="order_updated", obj=order,
              after={"total": str(order.total_amount)})
    return order


# ---------------------------------------------------------------- confirm / handover

@transaction.atomic
def confirm_order(*, order, user) -> SalesOrder:
    order = _lock(order)
    _require_order_staff(user, order, "confirm")
    if order.fulfillment_status not in EDITABLE_STATUSES:
        raise BusinessRuleError("invalid_state", f"{order.number} is {order.fulfillment_status}.")
    _check_credit(order, user)

    direct = {loc.pk: loc for loc in direct_locations(order.branch)}
    lines = list(order.lines.select_related("product", "source_location"))
    by_direct, by_warehouse = {}, {}
    for line in lines:
        target = by_direct if line.source_location_id in direct else by_warehouse
        target.setdefault(line.source_location_id, []).append(line)

    order.fulfillment_status = FulfillmentStatus.CONFIRMED
    order.confirmed_at, order.confirmed_by = timezone.now(), user
    order.save(update_fields=["fulfillment_status", "confirmed_at", "confirmed_by",
                              "updated_at"])

    for location_id, group in by_direct.items():
        _hand_over(order, direct[location_id], [(ln, ln.qty) for ln in group], user)

    from apps.requests.services import create_stock_request

    for group in by_warehouse.values():
        create_stock_request(
            requesting_location=order.branch, source_location=group[0].source_location,
            lines=[{"product": ln.product, "qty": ln.qty} for ln in group],
            salesperson=order.salesperson, customer=order.customer, order=order,
            reference=order.number, notes=order.notes)

    _refresh_fulfillment(order)
    payments.refresh_payment_status(order)
    audit_log(actor=user, action="order_confirmed", obj=order,
              after={"total": str(order.total_amount),
                     "unpaid": str(money.order_remaining(order))})
    return order


@transaction.atomic
def release_from_branch(*, order, lines, user) -> DeliveryNote:
    """Hand goods to the customer at the branch: first those held for this sale (arrived
    from the warehouse), then any free branch stock. lines = [{"line_id", "qty"}]."""
    order = _lock(order)
    if order.fulfillment_status not in BILLABLE_STATUSES:
        raise BusinessRuleError("invalid_state", f"{order.number} is {order.fulfillment_status}.")
    if not (user.role in (Role.ACCOUNTANT, Role.ADMIN)
            or user.home_location_id == order.branch_id):
        raise BusinessRuleError("wrong_location",
                                f"Only staff at {order.branch.code} hand over this sale.")
    order_lines = {ln.pk: ln for ln in order.lines.select_for_update(of=("self",))
                   .select_related("product")}
    if not lines:
        raise BusinessRuleError("no_lines", "Choose what to hand over.")
    held, free, seen = [], [], set()
    for item in lines:
        line = order_lines.get(item.get("line_id"))
        if line is None or line.pk in seen:
            raise BusinessRuleError("unknown_line", "Each line once, from this sale.")
        seen.add(line.pk)
        qty = _qty(item.get("qty"))
        if qty > line.qty_open:
            raise BusinessRuleError("qty_exceeds_order",
                                    f"{line.product.code}: only {line.qty_open} left to hand over.")
        from_held = min(qty, line.qty_awaiting)
        if from_held:
            held.append((line, from_held))
        if qty - from_held:
            free.append((line, qty - from_held))

    note = None
    if held:
        for line, qty in held:  # no longer held once handed over (keeps held ≤ still to deliver)
            line.qty_awaiting -= qty
            line.save(update_fields=["qty_awaiting"])
        note = _hand_over(order, order.branch, held, user, consume_reservation=True)
    if free:
        extra = _hand_over(order, order.branch, free, user)
        note = note or extra
    _refresh_fulfillment(order)
    audit_log(actor=user, action="order_handed_over", obj=order,
              after={line.product.code: qty for line, qty in held + free})
    return note


def on_transfer_received(*, transfer, received: dict) -> None:
    """Called by inventory.receive_transfer. Goods that arrive at the branch for a sale are
    held (reserved) there for that customer; the rest is ordinary branch stock."""
    order = transfer.stock_request.order if transfer.stock_request_id else None
    if order is None:
        return
    order = _lock(order)
    if order.fulfillment_status not in BILLABLE_STATUSES:
        return  # cancelled or voided: the goods stay as free branch stock
    for tline in transfer.lines.select_related("product"):
        qty = received.get(tline.pk, 0)
        if tline.condition != Condition.NEW:
            continue  # only new stock is requested for sales
        line = (order.lines.select_for_update()
                .filter(product=tline.product, condition=Condition.NEW).first())
        if not qty or line is None:
            continue
        hold = min(qty, line.qty_open - line.qty_awaiting)
        if hold > 0:
            inventory.reserve(product=line.product, location=transfer.to_location, qty=hold)
            line.qty_awaiting += hold
            line.save(update_fields=["qty_awaiting"])
    notify("order.goods_arrived", order, transfer=transfer)


def on_pickup_released(*, request, release, picked) -> None:
    """Called by requests.release_stock for a customer pickup: the goods went straight to
    the customer, so record the handover on the sale. picked = [(request_line, qty)]."""
    if request.order_id is None:
        return
    order = _lock(request.order)
    if order.fulfillment_status not in BILLABLE_STATUSES:
        raise BusinessRuleError("invalid_state", f"{order.number} is {order.fulfillment_status}.")
    note = DeliveryNote.objects.create(number=next_number(DELIVERY_NOTE), order=order,
                                       location=request.source_location,
                                       issued_by=release.released_by)
    for request_line, qty in picked:
        line = order.lines.select_for_update().get(product=request_line.product,
                                                   condition=Condition.NEW)
        if qty > line.qty_open - line.qty_awaiting:
            raise BusinessRuleError("qty_exceeds_order",
                                    f"{line.product.code}: the customer is owed only "
                                    f"{line.qty_open - line.qty_awaiting} more.")
        DeliveryNoteLine.objects.create(note=note, order_line=line, product=line.product,
                                        qty=qty)
        line.qty_released += qty
        line.save(update_fields=["qty_released"])
    _refresh_fulfillment(order)


@transaction.atomic
def mark_prepared(*, order, user) -> SalesOrder:
    """The warehouse has the goods ready (phone orders: Pending → Confirmed → Prepared)."""
    order = _lock(order)
    sources = set(order.lines.values_list("source_location_id", flat=True))
    if not (user.role == Role.ADMIN
            or (user.role == Role.STOREKEEPER and user.home_location_id in sources)):
        raise BusinessRuleError("permission_denied",
                                "Only the storekeeper supplying this sale marks it prepared.")
    if order.fulfillment_status != FulfillmentStatus.CONFIRMED:
        raise BusinessRuleError("invalid_state", f"{order.number} is {order.fulfillment_status}.")
    order.fulfillment_status = FulfillmentStatus.PREPARED
    order.save(update_fields=["fulfillment_status", "updated_at"])
    audit_log(actor=user, action="order_prepared", obj=order)
    notify("order.prepared", order)
    return order


@transaction.atomic
def request_stock_for_order(*, order, lines, user):
    """Ask the warehouse again for units nothing is yet bringing (after a rejected or short
    request). lines = [{"line_id", "qty"}]."""
    from apps.requests.services import create_stock_request

    order = _lock(order)
    _require_order_staff(user, order, "request stock for")
    if order.fulfillment_status not in BILLABLE_STATUSES:
        raise BusinessRuleError("invalid_state", f"{order.number} is {order.fulfillment_status}.")
    order_lines = {ln.pk: ln for ln in order.lines.select_related("product", "source_location")}
    picked, source = [], None
    for item in lines or []:
        line = order_lines.get(item.get("line_id"))
        if line is None:
            raise BusinessRuleError("unknown_line", "That line is not on this sale.")
        if not line.source_location.can_release:
            raise BusinessRuleError("invalid_source",
                                    f"{line.product.code} is sold from the branch, not requested.")
        if source is not None and line.source_location_id != source.pk:
            raise BusinessRuleError("invalid_source", "Request from one warehouse at a time.")
        source = line.source_location
        qty = _qty(item.get("qty"))
        need = still_needed(order, line)
        if qty > need:
            raise BusinessRuleError("qty_exceeds_order",
                                    f"{line.product.code}: only {need} still needed.")
        picked.append({"product": line.product, "qty": qty})
    if not picked:
        raise BusinessRuleError("no_lines", "Choose what to request.")
    return create_stock_request(
        requesting_location=order.branch, source_location=source, lines=picked,
        salesperson=order.salesperson, customer=order.customer, order=order,
        reference=order.number)


# ---------------------------------------------------------------- cancel / void / return

@transaction.atomic
def cancel_order(*, order, user, reason: str) -> SalesOrder:
    """Stop a sale before anything is handed to the customer. Its payments become the
    customer's advance; goods held or on the way for it become ordinary stock."""
    reason = _require_reason(reason)
    order = _lock(order)
    _require_order_staff(user, order, "cancel")
    if order.fulfillment_status not in EDITABLE_STATUSES + BILLABLE_STATUSES:
        raise BusinessRuleError("invalid_state", f"{order.number} is {order.fulfillment_status}.")
    if order.lines.filter(qty_released__gt=0).exists():
        raise BusinessRuleError("already_released",
                                "Goods were handed over; use a return or void instead.")
    _close_open_requests(order, user, f"Sale {order.number} cancelled: {reason}")
    _free_awaiting(order)
    order.fulfillment_status = FulfillmentStatus.CANCELLED
    order.closed_at, order.closed_by, order.close_reason = timezone.now(), user, reason
    order.save(update_fields=["fulfillment_status", "closed_at", "closed_by", "close_reason",
                              "updated_at"])
    payments.release_order_allocations(order=order, reason=f"Sale cancelled: {reason}")
    audit_log(actor=user, action="order_cancelled", obj=order, reason=reason)
    notify("order.cancelled", order)
    return order


@transaction.atomic
def void_order(*, order, user, reason: str) -> SalesOrder:
    """Correct a sale entered wrongly (D6): stock goes back where it came from, the sale
    leaves the customer's balance, its payments become the customer's advance. Re-issue the
    correct sale with create_order(replaces=…)."""
    reason = _require_reason(reason)
    if not user.has_erp_permission(ERPPermission.CORRECT_TRANSACTIONS):
        raise BusinessRuleError("permission_denied", "You are not allowed to void sales.")
    order = _lock(order)
    if order.fulfillment_status not in BILLABLE_STATUSES:
        raise BusinessRuleError("invalid_state", f"{order.number} is {order.fulfillment_status}.")
    if order.returns.exists():
        raise BusinessRuleError("has_returns",
                                "Goods were already returned on this sale; it cannot be voided.")
    sales = list(StockMovement.objects.filter(transaction_number=order.number,
                                              type=MovementType.SALE)
                 .filter(Q(reversed_by__isnull=True)))
    for movement in sales:
        inventory.reverse_movement(movement=movement, person=user, internal=True,
                                   reason=f"Void {order.number}: {reason}")
    _close_open_requests(order, user, f"Sale {order.number} voided: {reason}")
    _free_awaiting(order)
    order.fulfillment_status = FulfillmentStatus.VOIDED
    order.closed_at, order.closed_by, order.close_reason = timezone.now(), user, reason
    order.save(update_fields=["fulfillment_status", "closed_at", "closed_by", "close_reason",
                              "updated_at"])
    payments.release_order_allocations(order=order, reason=f"Sale voided: {reason}")
    audit_log(actor=user, action="order_voided", obj=order, reason=reason,
              after={"reversed_movements": [m.number for m in sales]})
    return order


def _returned_value(line, qty_returned_total: int) -> Decimal:
    """Value of the first `qty_returned_total` units of a line, discount spread evenly.
    Computed cumulatively so a fully returned line gives back exactly its line total."""
    return (line.line_total * qty_returned_total / line.qty).quantize(CENT, ROUND_HALF_UP)


@transaction.atomic
def return_goods(*, order, lines, location, user, reason: str) -> SalesReturn:
    """The customer brings goods back: stock returns to `location` (into the damaged count
    when a line says `"condition": "damaged"`), the sale's total drops, and money already paid
    beyond the new total becomes the customer's advance."""
    reason = _require_reason(reason)
    if user.role not in (Role.ACCOUNTANT, Role.ADMIN):
        raise BusinessRuleError("permission_denied", "Only the accountant records returns.")
    order = _lock(order)
    if order.fulfillment_status not in BILLABLE_STATUSES:
        raise BusinessRuleError("invalid_state", f"{order.number} is {order.fulfillment_status}.")
    if location.code == TRANSIT_CODE or not location.is_active:
        raise BusinessRuleError("invalid_location", f"{location.code} cannot take returns.")
    order_lines = {ln.pk: ln for ln in order.lines.select_for_update(of=("self",))
                   .select_related("product")}
    picked, seen = [], set()
    for item in lines or []:
        line = order_lines.get(item.get("line_id"))
        if line is None or line.pk in seen:
            raise BusinessRuleError("unknown_line", "Each line once, from this sale.")
        seen.add(line.pk)
        qty = _qty(item.get("qty"))
        if qty > line.qty_released - line.qty_returned:
            raise BusinessRuleError(
                "qty_exceeds_order",
                f"{line.product.code}: only {line.qty_released - line.qty_returned} "
                f"can be returned.")
        condition = item.get("condition") or Condition.NEW
        if condition not in Condition.values:
            raise BusinessRuleError("invalid_condition", "Choose new, display or damaged.")
        picked.append((line, qty, condition))
    if not picked:
        raise BusinessRuleError("no_lines", "Choose what is returned.")

    ret = SalesReturn.objects.create(number=next_number(SALES_RETURN), order=order,
                                     location=location, amount=Decimal("0"), reason=reason,
                                     created_by=user)
    total = Decimal("0")
    for line, qty, condition in picked:
        amount = (_returned_value(line, line.qty_returned + qty)
                  - _returned_value(line, line.qty_returned))
        SalesReturnLine.objects.create(sales_return=ret, order_line=line, product=line.product,
                                       qty=qty, amount=amount)
        inventory.post_movement(
            product=line.product, qty=qty, type=MovementType.RETURN, to_location=location,
            customer=order.customer, reference_type="sales_return", reference_id=ret.number,
            transaction_number=order.number, person=user, note=reason[:255],
            condition=condition)
        line.qty_returned += qty
        line.save(update_fields=["qty_returned"])
        total += amount
    ret.amount = total
    ret.save(update_fields=["amount"])

    recompute_total(order)
    excess = money.order_paid(order) - order.total_amount
    if excess > 0:
        payments.shrink_order_allocations(order=order, excess=excess, user=user,
                                          reason=f"Return {ret.number}")
    payments.refresh_payment_status(order)
    audit_log(actor=user, action="goods_returned", obj=order, reason=reason,
              after={"return": ret.number, "amount": str(total)})
    return ret
