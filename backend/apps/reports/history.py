"""The full history of one transaction, found from any of its numbers (D4)."""

from django.http import Http404

from apps.audit.models import AuditLog
from apps.inventory.models import StockMovement, StockTransfer
from apps.payments import selectors as money
from apps.payments.api.serializers import payment_dict
from apps.payments.models import Payment
from apps.requests.models import StockRelease, StockRequest
from apps.requests.selectors import requests_for_user
from apps.sales.models import DeliveryNote, SalesOrder, SalesReturn
from apps.sales.selectors import orders_for_user


def _name(user):
    return user.full_name if user else "system"


def resolve(number: str) -> str:
    """Any document number → the transaction number it belongs to."""
    number = number.strip().upper()
    if SalesOrder.objects.filter(number=number).exists():
        return number
    for model, field in ((DeliveryNote, "order__number"), (SalesReturn, "order__number")):
        found = model.objects.filter(number=number).values_list(field, flat=True).first()
        if found:
            return found
    for model in (StockRequest, StockRelease, StockTransfer, StockMovement):
        found = (model.objects.filter(number=number)
                 .values_list("transaction_number", flat=True).first())
        if found:
            return found
    payment = Payment.objects.filter(number=number).first()
    if payment:
        order = payment.allocations.order_by("id").values_list("order__number", flat=True).first()
        return order or payment.number
    raise Http404(f"No document numbered {number}.")


def _order_events(order) -> list[dict]:
    events = [{"at": order.created_at, "event": "created", "by": _name(order.created_by),
               "detail": f"{order.channel}, {order.receipt_type} receipt, "
                         f"total {order.total_amount}"}]
    if order.confirmed_at:
        events.append({"at": order.confirmed_at, "event": "confirmed",
                       "by": _name(order.confirmed_by), "detail": ""})
    if order.closed_at:
        events.append({"at": order.closed_at, "event": order.fulfillment_status,
                       "by": _name(order.closed_by), "detail": order.close_reason})
    for log in AuditLog.objects.filter(model="sales.SalesOrder", object_id=str(order.pk),
                                       action__in=["order_prepared"]):
        events.append({"at": log.at, "event": "prepared", "by": _name(log.actor), "detail": ""})
    for note in order.delivery_notes.select_related("location", "issued_by"):
        items = ", ".join(f"{ln.qty} × {ln.product.code}"
                          for ln in note.lines.select_related("product"))
        events.append({"at": note.issued_at, "event": "handed over", "by": _name(note.issued_by),
                       "detail": f"{note.number} at {note.location.code}: {items}",
                       "number": note.number})
    for ret in order.returns.select_related("created_by", "location"):
        events.append({"at": ret.created_at, "event": "returned", "by": _name(ret.created_by),
                       "detail": f"{ret.number} to {ret.location.code}, {ret.amount}: "
                                 f"{ret.reason}", "number": ret.number})
    if hasattr(order, "replaced_by"):
        events.append({"at": order.replaced_by.created_at, "event": "re-issued",
                       "by": _name(order.replaced_by.created_by),
                       "detail": f"as {order.replaced_by.number}",
                       "number": order.replaced_by.number})
    return events


def _request_events(request) -> list[dict]:
    lines = ", ".join(f"{ln.qty_requested} × {ln.product.code}"
                      for ln in request.lines.select_related("product"))
    events = [{"at": request.created_at, "event": "stock requested",
               "by": _name(request.salesperson),
               "detail": f"{request.number}: {lines} from {request.source_location.code}",
               "number": request.number}]
    if request.acknowledged_at:
        events.append({"at": request.acknowledged_at, "event": "acknowledged",
                       "by": _name(request.acknowledged_by), "detail": request.number,
                       "number": request.number})
    for release in request.releases.select_related("released_by", "transfer"):
        items = ", ".join(f"{ln.qty} × {ln.product.code}"
                          for ln in release.lines.select_related("product"))
        events.append({"at": release.released_at, "event": "released",
                       "by": _name(release.released_by),
                       "detail": f"{release.number} ({release.destination_type}): {items}",
                       "number": release.number})
    if request.closed_at:
        events.append({"at": request.closed_at, "event": f"request {request.status}",
                       "by": _name(request.closed_by),
                       "detail": f"{request.number}: {request.close_reason}",
                       "number": request.number})
    for transfer in request.transfers.select_related("received_by", "to_location"):
        if transfer.received_at:
            events.append({"at": transfer.received_at, "event": "received",
                           "by": _name(transfer.received_by),
                           "detail": f"{transfer.number} at {transfer.to_location.code}"
                                     + (f" — {transfer.discrepancy_note}"
                                        if transfer.discrepancy_note else ""),
                           "number": transfer.number})
    return events


def _payment_events(payment, user) -> list[dict]:
    shown = payment_dict(payment, user)
    amount = shown["amount"] or "(hidden)"
    events = [{"at": payment.created_at, "event": "payment recorded",
               "by": _name(payment.recorded_by),
               "detail": f"{payment.number}: {amount} to {payment.account.kind}"
                         + (f", receipt {payment.receipt_number}"
                            if payment.receipt_number else "")
                         + (f" (corrects {payment.replaces.number})"
                            if payment.replaces_id else ""),
               "number": payment.number}]
    if payment.verified_at and payment.verified_by_id != payment.recorded_by_id:
        events.append({"at": payment.verified_at, "event": "payment verified",
                       "by": _name(payment.verified_by), "detail": payment.number,
                       "number": payment.number})
    if payment.closed_at:
        events.append({"at": payment.closed_at, "event": f"payment {payment.status}",
                       "by": _name(payment.closed_by),
                       "detail": f"{payment.number}: {payment.close_reason}",
                       "number": payment.number})
    return events


def transaction_history(number: str, user) -> dict:
    """Header + chronological events for the transaction `number` belongs to. 404 when it
    does not exist or the user may not see it."""
    txn = resolve(number)
    order = orders_for_user(user).filter(number=txn).first()
    if order is not None:
        requests = list(order.stock_requests.select_related("source_location", "salesperson"))
        payments = list(Payment.objects.filter(allocations__order=order).distinct()
                        .select_related("account", "recorded_by", "customer", "replaces"))
        events = _order_events(order)
        for request in requests:
            events += _request_events(request)
        for payment in payments:
            events += _payment_events(payment, user)
        paid = money.order_paid(order)
        header = {
            "transaction": order.number, "kind": "sale", "customer": order.customer.name,
            "salesperson": order.salesperson.full_name, "branch": order.branch.code,
            "status": order.fulfillment_status, "payment_status": order.payment_status,
            "receipt_type": order.receipt_type, "total": str(order.total_amount),
            "paid": str(paid), "remaining": str(order.total_amount - paid),
            "replaces": order.replaces.number if order.replaces_id else None,
            "products": [{"code": ln.product.code, "name": ln.product.name, "qty": ln.qty,
                          "released": ln.qty_released, "returned": ln.qty_returned,
                          "source": ln.source_location.code}
                         for ln in order.lines.select_related("product", "source_location")],
        }
    else:
        request = requests_for_user(user).filter(transaction_number=txn, order__isnull=True).first()
        payment = None if request else Payment.objects.filter(number=txn).first()
        if request is not None:
            events = _request_events(request)
            header = {"transaction": txn, "kind": "stock request",
                      "status": request.status, "branch": request.requesting_location.code,
                      "source": request.source_location.code,
                      "salesperson": request.salesperson.full_name,
                      "customer": request.customer.name if request.customer else None,
                      "products": [{"code": ln.product.code, "name": ln.product.name,
                                    "qty": ln.qty_requested, "released": ln.qty_released}
                                   for ln in request.lines.select_related("product")]}
        elif payment is not None and money.payments_for_user(user).filter(pk=payment.pk).exists():
            events = _payment_events(payment, user)
            header = {"transaction": txn, "kind": "payment",
                      "customer": payment.customer.name, "status": payment.status}
        else:
            raise Http404("Not found.")
    events.sort(key=lambda e: e["at"])
    return {"header": header, "events": events}
