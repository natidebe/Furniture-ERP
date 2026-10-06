from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Product
from apps.customers.models import Customer
from apps.inventory.models import Condition
from apps.locations.models import Location
from apps.payments import selectors as money
from apps.payments.api.serializers import payment_dict
from apps.payments.models import PaymentAccount, PaymentMethod
from apps.sales.models import Channel, DeliveryNote, ReceiptType, SalesOrder

CONDITIONS = Condition.choices


class OrderLineInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    qty = serializers.IntegerField(min_value=1)
    condition = serializers.ChoiceField(choices=CONDITIONS, default="new")
    discount = serializers.DecimalField(max_digits=14, decimal_places=2,
                                        min_value=Decimal("0"), required=False,
                                        default=Decimal("0"))
    source_location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(),
                                                         required=False)


class PaymentNowSerializer(serializers.Serializer):
    account = serializers.PrimaryKeyRelatedField(queryset=PaymentAccount.objects.all())
    amount = serializers.DecimalField(max_digits=14, decimal_places=2,
                                      min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    receipt_number = serializers.CharField(max_length=50, required=False, allow_blank=True,
                                           allow_null=True)
    paid_at = serializers.DateTimeField(required=False)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class OrderCreateSerializer(serializers.Serializer):
    """`branch` defaults to your branch. Prices always come from the product (D11)."""

    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    branch = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(), required=False)
    channel = serializers.ChoiceField(choices=Channel.choices, default=Channel.WALK_IN)
    receipt_type = serializers.ChoiceField(choices=ReceiptType.choices,
                                           default=ReceiptType.NONE)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lines = OrderLineInputSerializer(many=True, allow_empty=False)
    payment = PaymentNowSerializer(required=False)
    replaces = serializers.PrimaryKeyRelatedField(queryset=SalesOrder.objects.all(),
                                                  required=False)


class OrderUpdateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(),
                                                  required=False)
    receipt_type = serializers.ChoiceField(choices=ReceiptType.choices, required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
    lines = OrderLineInputSerializer(many=True, required=False, allow_empty=False)


class LineQtySerializer(serializers.Serializer):
    line_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=1)


class LinesSerializer(serializers.Serializer):
    lines = LineQtySerializer(many=True, allow_empty=False)


class ReturnLineSerializer(LineQtySerializer):
    condition = serializers.ChoiceField(choices=CONDITIONS, default="new")


class ReturnSerializer(serializers.Serializer):
    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all())
    reason = serializers.CharField(max_length=500)
    lines = ReturnLineSerializer(many=True, allow_empty=False)


class OrderReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[("prepared", "prepared")])


def delivery_note_dict(note) -> dict:
    return {
        "id": note.pk, "number": note.number, "location_code": note.location.code,
        "issued_by_name": note.issued_by.full_name, "issued_at": note.issued_at,
        "lines": [{"product_code": ln.product.code, "product_name": ln.product.name,
                   "qty": ln.qty} for ln in note.lines.select_related("product")],
    }


def order_dict(order, user, *, detail=True) -> dict:
    paid = money.order_paid(order)
    data = {
        "id": order.pk,
        "number": order.number,
        "customer": order.customer_id,
        "customer_name": order.customer.name,
        "customer_type": order.customer.type,
        "branch": order.branch_id,
        "branch_code": order.branch.code,
        "salesperson": order.salesperson_id,
        "salesperson_name": order.salesperson.full_name,
        "channel": order.channel,
        "receipt_type": order.receipt_type,
        "fulfillment_status": order.fulfillment_status,
        "payment_status": order.payment_status,
        "total": str(order.total_amount),
        "paid": str(paid),
        "remaining": str(order.total_amount - paid),
        "notes": order.notes,
        "created_at": order.created_at,
        "confirmed_at": order.confirmed_at,
        "closed_at": order.closed_at,
        "close_reason": order.close_reason,
        "replaces": order.replaces.number if order.replaces_id else None,
        "replaced_by": getattr(getattr(order, "replaced_by", None), "number", None),
    }
    if not detail:
        return data
    data["lines"] = [{
        "id": line.pk, "product": line.product_id, "product_code": line.product.code,
        "product_name": line.product.name, "condition": line.condition, "qty": line.qty,
        "unit_price": str(line.unit_price),
        "discount": str(line.discount), "line_total": str(line.line_total),
        "source_location_code": line.source_location.code,
        "qty_released": line.qty_released, "qty_awaiting": line.qty_awaiting,
        "qty_returned": line.qty_returned,
        "paid": str(money.line_paid(line)), "remaining": str(money.line_remaining(line)),
    } for line in order.lines.select_related("product", "source_location")]
    data["delivery_notes"] = [delivery_note_dict(n) for n in
                              order.delivery_notes.select_related("location", "issued_by")]
    data["stock_requests"] = [{"id": r.pk, "number": r.number, "status": r.status,
                               "source_location_code": r.source_location.code}
                              for r in order.stock_requests.select_related("source_location")]
    data["returns"] = [{"number": r.number, "amount": str(r.amount), "reason": r.reason,
                        "created_at": r.created_at} for r in order.returns.all()]
    return data


def order_payments_dict(order, user) -> dict:
    from apps.payments.models import Payment

    payments = (Payment.objects.filter(allocations__order=order).distinct()
                .select_related("customer", "account", "recorded_by", "replaces")
                .order_by("paid_at", "id"))
    paid = money.order_paid(order)
    return {
        "order": order.number, "total": str(order.total_amount), "paid": str(paid),
        "remaining": str(order.total_amount - paid), "payment_status": order.payment_status,
        "payments": [payment_dict(p, user) for p in payments],
    }


class OrderOutputSerializer(serializers.Serializer):
    """Schema only; the data comes from order_dict()."""

    id = serializers.IntegerField()
    number = serializers.CharField()
    customer = serializers.IntegerField()
    customer_name = serializers.CharField()
    branch_code = serializers.CharField()
    salesperson_name = serializers.CharField()
    channel = serializers.CharField()
    receipt_type = serializers.CharField()
    fulfillment_status = serializers.CharField()
    payment_status = serializers.CharField()
    total = serializers.CharField()
    paid = serializers.CharField()
    remaining = serializers.CharField()
    lines = serializers.ListField(child=serializers.DictField(), required=False)
    delivery_notes = serializers.ListField(child=serializers.DictField(), required=False)
    stock_requests = serializers.ListField(child=serializers.DictField(), required=False)


class DeliveryNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryNote
        fields = ["id", "number", "order", "location", "issued_by", "issued_at"]
