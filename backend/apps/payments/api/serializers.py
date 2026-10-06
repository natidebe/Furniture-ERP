from decimal import Decimal

from rest_framework import serializers

from apps.customers.models import Customer
from apps.payments import selectors
from apps.payments.models import PaymentAccount, PaymentMethod
from apps.sales.models import SalesOrder, SalesOrderLine


class PaymentAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentAccount
        fields = ["id", "name", "kind", "method", "bank_name", "account_number", "owner_name",
                  "is_active"]


class AllocationInputSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(queryset=SalesOrder.objects.all())
    line = serializers.PrimaryKeyRelatedField(queryset=SalesOrderLine.objects.all(),
                                              required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2,
                                      min_value=Decimal("0.01"))


class PaymentInputSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    account = serializers.PrimaryKeyRelatedField(queryset=PaymentAccount.objects.all())
    amount = serializers.DecimalField(max_digits=14, decimal_places=2,
                                      min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    receipt_number = serializers.CharField(max_length=50, required=False, allow_blank=True,
                                           allow_null=True)
    paid_at = serializers.DateTimeField(required=False)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    allocations = AllocationInputSerializer(many=True, required=False, default=list)


class AllocateSerializer(serializers.Serializer):
    allocations = AllocationInputSerializer(many=True, allow_empty=False)


class PaymentReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class CorrectPaymentSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2,
                                      min_value=Decimal("0.01"), required=False)
    account = serializers.PrimaryKeyRelatedField(queryset=PaymentAccount.objects.all(),
                                                 required=False)
    method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False)
    receipt_number = serializers.CharField(max_length=50, required=False, allow_blank=True,
                                           allow_null=True)
    paid_at = serializers.DateTimeField(required=False)
    allocations = AllocationInputSerializer(many=True, required=False)


def payment_dict(payment, user) -> dict:
    """A payment as the API shows it. Personal-account amounts are hidden from users without
    view_personal_payments (except the person who recorded it)."""
    visible = selectors.can_see_amount(user, payment)
    allocations = [
        {"order": a.order_id, "order_number": a.order.number,
         "line": a.order_line_id,
         "product_code": a.order_line.product.code if a.order_line_id else None,
         "amount": str(a.amount) if visible else None, "is_active": a.is_active,
         "deactivated_reason": a.deactivated_reason}
        for a in payment.allocations.select_related("order", "order_line__product")
    ]
    return {
        "id": payment.pk,
        "number": payment.number,
        "customer": payment.customer_id,
        "customer_name": payment.customer.name,
        "amount": str(payment.amount) if visible else None,
        "unallocated": str(selectors.payment_unallocated(payment)) if visible else None,
        "account": payment.account_id if visible else None,
        "account_name": payment.account.name if visible else None,
        "account_kind": payment.account.kind,
        "method": payment.method,
        "receipt_number": payment.receipt_number,
        "paid_at": payment.paid_at,
        "status": payment.status,
        "recorded_by": payment.recorded_by_id,
        "recorded_by_name": payment.recorded_by.full_name,
        "recorded_at": payment.created_at,
        "verified_by": payment.verified_by_id,
        "verified_at": payment.verified_at,
        "closed_by": payment.closed_by_id,
        "closed_at": payment.closed_at,
        "close_reason": payment.close_reason,
        "replaces": payment.replaces.number if payment.replaces_id else None,
        "replaced_by": getattr(getattr(payment, "replaced_by", None), "number", None),
        "note": payment.note,
        "hidden": not visible,
        "allocations": allocations,
    }


class PaymentOutputSerializer(serializers.Serializer):
    """Schema only; the data comes from payment_dict()."""

    id = serializers.IntegerField()
    number = serializers.CharField()
    customer = serializers.IntegerField()
    customer_name = serializers.CharField()
    amount = serializers.CharField(allow_null=True)
    unallocated = serializers.CharField(allow_null=True)
    account = serializers.IntegerField(allow_null=True)
    account_name = serializers.CharField(allow_null=True)
    account_kind = serializers.CharField()
    method = serializers.CharField()
    receipt_number = serializers.CharField(allow_null=True)
    paid_at = serializers.DateTimeField()
    status = serializers.CharField()
    recorded_by = serializers.IntegerField()
    recorded_by_name = serializers.CharField()
    recorded_at = serializers.DateTimeField()
    verified_by = serializers.IntegerField(allow_null=True)
    verified_at = serializers.DateTimeField(allow_null=True)
    closed_by = serializers.IntegerField(allow_null=True)
    closed_at = serializers.DateTimeField(allow_null=True)
    close_reason = serializers.CharField()
    replaces = serializers.CharField(allow_null=True)
    replaced_by = serializers.CharField(allow_null=True)
    note = serializers.CharField()
    hidden = serializers.BooleanField()
    allocations = serializers.ListField(child=serializers.DictField())
