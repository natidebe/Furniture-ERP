"""Stock requests: the only way stock leaves the warehouse (BUILD_PHASES.md 2.3).

pending ──acknowledge──▶ acknowledged ──release(partial)──▶ partially_released
   │                         │                                  │
   │                         └──release(all)──▶ released ◀──────┘
   ├──reject──▶ rejected     (pending / acknowledged)           │
   └──cancel──▶ cancelled    (before any release)       close──▶ closed
                              partially_released also closes, freeing what is left.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.services import audit_log
from apps.core.exceptions import BusinessRuleError
from apps.core.numbering import STOCK_RELEASE, STOCK_REQUEST, next_number
from apps.inventory import services as inventory
from apps.inventory.models import TRANSIT_CODE, MovementType
from apps.notifications.services import notify

from .models import (
    DestinationType,
    RequestStatus,
    StockRelease,
    StockReleaseLine,
    StockRequest,
    StockRequestLine,
)


def _lock(request) -> StockRequest:
    return StockRequest.objects.select_for_update(of=("self",)).select_related(
        "source_location", "requesting_location", "customer").get(pk=request.pk)


def _require_source_storekeeper(user, request, action: str):
    if user.role == Role.ADMIN:
        return
    if user.role == Role.STOREKEEPER and user.home_location_id == request.source_location_id:
        return
    raise BusinessRuleError("wrong_location",
                            f"Only the {request.source_location.code} storekeeper can {action}.")


def _free_remaining(request, user, reason: str, new_status: str):
    """Release every unreleased reservation and move the request to a closed status."""
    for line in request.lines.select_for_update(of=("self",)).select_related("product"):
        if line.qty_remaining:
            inventory.unreserve(product=line.product, location=request.source_location,
                                qty=line.qty_remaining)
    request.status = new_status
    request.closed_by, request.closed_at = user, timezone.now()
    request.close_reason = reason
    request.save(update_fields=["status", "closed_by", "closed_at", "close_reason"])


@transaction.atomic
def create_stock_request(*, requesting_location, source_location, lines, salesperson,
                         customer=None, reference="", notes="", order=None) -> StockRequest:
    """lines = [{"product": Product, "qty": int}]. Reserves every line at the source.

    Storekeepers cannot create requests: the person who releases stock must never be the
    one who asked for it. A request made by a sale (`order`) carries that sale's authority:
    it is for the sale's branch and customer and uses the sale's number (D4).
    """
    if order is not None:
        if requesting_location.pk != order.branch_id:
            raise BusinessRuleError("wrong_location", "A sale's stock goes to its own branch.")
        customer = order.customer
    elif salesperson.role not in (Role.SALESPERSON, Role.ADMIN):
        raise BusinessRuleError("permission_denied", "Only sales staff can request stock.")
    elif salesperson.role == Role.SALESPERSON \
            and salesperson.home_location_id != requesting_location.pk:
        raise BusinessRuleError("wrong_location",
                                "You can only request stock for your own branch.")
    for loc in (requesting_location, source_location):
        if loc.code == TRANSIT_CODE or not loc.is_active:
            raise BusinessRuleError("invalid_location", f"{loc.code} cannot be used here.")
    if not source_location.can_release:
        raise BusinessRuleError("invalid_location",
                                f"{source_location.code} does not release stock.")
    if requesting_location.pk == source_location.pk:
        raise BusinessRuleError("same_location", "A location cannot request from itself.")
    inventory.check_lines(lines)
    for line in lines:
        if not line["product"].is_active:
            raise BusinessRuleError("inactive_product", f"{line['product'].code} is not active.")

    number = next_number(STOCK_REQUEST)
    request = StockRequest.objects.create(
        number=number, requesting_location=requesting_location,
        source_location=source_location,
        transaction_number=order.number if order is not None else number,
        order=order, customer=customer, reference=reference, salesperson=salesperson,
        notes=notes)
    for line in lines:
        StockRequestLine.objects.create(request=request, product=line["product"],
                                        qty_requested=line["qty"])
        inventory.reserve(product=line["product"], location=source_location, qty=line["qty"])
    notify("stock_request.created", request)
    return request


@transaction.atomic
def acknowledge_request(*, request, user) -> StockRequest:
    request = _lock(request)
    _require_source_storekeeper(user, request, "acknowledge this request")
    if request.status != RequestStatus.PENDING:
        raise BusinessRuleError("invalid_state", f"{request.number} is {request.status}.")
    request.status = RequestStatus.ACKNOWLEDGED
    request.acknowledged_by, request.acknowledged_at = user, timezone.now()
    request.save(update_fields=["status", "acknowledged_by", "acknowledged_at"])
    notify("stock_request.acknowledged", request)
    return request


@transaction.atomic
def release_stock(*, request, lines, storekeeper, destination_type, note="") -> StockRelease:
    """Record what the storekeeper actually took out. lines = [{"line_id", "qty"}].

    To a branch: a transfer Pawlos → TRANSIT (received later at the branch).
    Customer pickup: a sale Pawlos → customer. Both use the request's own reservation.
    """
    request = _lock(request)
    _require_source_storekeeper(user=storekeeper, request=request, action="release stock")
    if request.status not in (RequestStatus.ACKNOWLEDGED, RequestStatus.PARTIALLY_RELEASED):
        raise BusinessRuleError("invalid_state",
                                f"{request.number} is {request.status}, not open for release.")
    if destination_type not in DestinationType.values:
        raise BusinessRuleError("invalid_destination", "Choose branch or customer pickup.")
    if destination_type == DestinationType.CUSTOMER_PICKUP and request.customer is None:
        raise BusinessRuleError("customer_required",
                                "A customer pickup needs the request to name the customer.")
    if not lines:
        raise BusinessRuleError("no_lines", "Release at least one line.")

    request_lines = {line.pk: line for line in
                     request.lines.select_for_update(of=("self",)).select_related("product")}
    picked = []
    seen = set()
    for item in lines:
        line = request_lines.get(item.get("line_id"))
        if line is None:
            raise BusinessRuleError("unknown_line", f"Line {item.get('line_id')} is not on "
                                                    f"{request.number}.")
        if line.pk in seen:
            raise BusinessRuleError("duplicate_line", f"{line.product.code} is listed twice.")
        seen.add(line.pk)
        qty = item.get("qty")
        if not isinstance(qty, int) or isinstance(qty, bool) or not 0 < qty <= line.qty_remaining:
            raise BusinessRuleError(
                "qty_exceeds_request",
                f"{line.product.code}: release between 1 and {line.qty_remaining}.")
        picked.append((line, qty))

    release = StockRelease.objects.create(
        number=next_number(STOCK_RELEASE), request=request,
        transaction_number=request.transaction_number, destination_type=destination_type,
        released_by=storekeeper, note=note)
    for line, qty in picked:
        StockReleaseLine.objects.create(release=release, request_line=line,
                                        product=line.product, qty=qty)

    if destination_type == DestinationType.BRANCH:
        transfer = inventory.send_transfer(
            from_location=request.source_location, to_location=request.requesting_location,
            lines=[{"product": line.product, "qty": qty} for line, qty in picked],
            user=storekeeper, stock_request=request,
            transaction_number=request.transaction_number, consume_reservation=True,
            note=f"Release {release.number}")
        release.transfer = transfer
        release.save(update_fields=["transfer"])
    else:
        for line, qty in picked:
            inventory.post_movement(
                product=line.product, qty=qty, type=MovementType.SALE,
                from_location=request.source_location, customer=request.customer,
                reference_type="stock_release", reference_id=release.number,
                transaction_number=request.transaction_number, person=storekeeper,
                consume_reservation=True)
        if request.order_id:
            from apps.sales.services import on_pickup_released

            on_pickup_released(request=request, release=release, picked=picked)

    for line, qty in picked:
        line.qty_released += qty
        line.save(update_fields=["qty_released"])

    done = all(line.qty_remaining == 0 for line in request_lines.values())
    request.status = RequestStatus.RELEASED if done else RequestStatus.PARTIALLY_RELEASED
    request.save(update_fields=["status"])
    notify("stock_request.released", request, release=release)
    return release


@transaction.atomic
def reject_request(*, request, user, reason: str) -> StockRequest:
    reason = (reason or "").strip()
    if not reason:
        raise BusinessRuleError("reason_required", "Give a reason for rejecting.")
    request = _lock(request)
    _require_source_storekeeper(user, request, "reject this request")
    if request.status not in (RequestStatus.PENDING, RequestStatus.ACKNOWLEDGED):
        raise BusinessRuleError("invalid_state", f"{request.number} is {request.status}.")
    _free_remaining(request, user, reason, RequestStatus.REJECTED)
    audit_log(actor=user, action="stock_request_rejected", obj=request, reason=reason)
    notify("stock_request.rejected", request)
    return request


@transaction.atomic
def cancel_request(*, request, user, reason: str) -> StockRequest:
    """The requesting salesperson (or an admin) withdraws a request before any release."""
    reason = (reason or "").strip()
    if not reason:
        raise BusinessRuleError("reason_required", "Give a reason for cancelling.")
    request = _lock(request)
    if not (user.role == Role.ADMIN or user.pk == request.salesperson_id):
        raise BusinessRuleError("permission_denied", "Only the requester can cancel this.")
    if request.status not in (RequestStatus.PENDING, RequestStatus.ACKNOWLEDGED):
        raise BusinessRuleError("invalid_state",
                                f"{request.number} is {request.status}; close it instead.")
    _free_remaining(request, user, reason, RequestStatus.CANCELLED)
    audit_log(actor=user, action="stock_request_cancelled", obj=request, reason=reason)
    notify("stock_request.cancelled", request)
    return request


@transaction.atomic
def close_for_order(*, request, user, reason: str) -> StockRequest:
    """A sale was cancelled or voided: stop its request whatever its state and free what is
    still reserved (cancelled before any release, closed after one)."""
    request = _lock(request)
    if not request.is_open:
        return request
    released = request.lines.filter(qty_released__gt=0).exists()
    _free_remaining(request, user, reason,
                    RequestStatus.CLOSED if released else RequestStatus.CANCELLED)
    audit_log(actor=user, action="stock_request_closed", obj=request, reason=reason)
    notify("stock_request.cancelled", request)
    return request


@transaction.atomic
def close_request(*, request, user, reason: str) -> StockRequest:
    """Finish a request: a partly released one gives back what was not released."""
    reason = (reason or "").strip()
    if not reason:
        raise BusinessRuleError("reason_required", "Give a reason for closing.")
    request = _lock(request)
    allowed = (user.role == Role.ADMIN or user.pk == request.salesperson_id
               or (user.role == Role.STOREKEEPER
                   and user.home_location_id == request.source_location_id))
    if not allowed:
        raise BusinessRuleError("permission_denied", "You cannot close this request.")
    if request.status not in (RequestStatus.PARTIALLY_RELEASED, RequestStatus.RELEASED):
        raise BusinessRuleError("invalid_state", f"{request.number} is {request.status}.")
    _free_remaining(request, user, reason, RequestStatus.CLOSED)
    audit_log(actor=user, action="stock_request_closed", obj=request, reason=reason)
    return request
