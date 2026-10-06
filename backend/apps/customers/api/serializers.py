from decimal import Decimal

from rest_framework import serializers

from apps.customers.models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    """Credit fields are read-only unless the user has approve_credit."""

    credit_limit = serializers.DecimalField(max_digits=14, decimal_places=2,
                                            min_value=Decimal("0"), required=False,
                                            allow_null=True)

    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "shop_name", "city", "type", "credit_allowed",
                  "credit_limit", "notes", "is_active", "created_at"]
        read_only_fields = ["created_at"]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        user = getattr(request, "user", None)
        can_set_credit = getattr(user, "has_erp_permission", lambda _p: False)("approve_credit")
        if not can_set_credit:
            fields["credit_allowed"].read_only = True
            fields["credit_limit"].read_only = True
        return fields


class CustomerBalanceSerializer(serializers.Serializer):
    total_purchases = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_paid = serializers.DecimalField(max_digits=14, decimal_places=2)
    outstanding = serializers.DecimalField(max_digits=14, decimal_places=2)
    prepaid = serializers.DecimalField(max_digits=14, decimal_places=2)
    unallocated = serializers.DecimalField(max_digits=14, decimal_places=2)


class StatementRowSerializer(serializers.Serializer):
    date = serializers.DateTimeField()
    kind = serializers.CharField()
    number = serializers.CharField()
    description = serializers.CharField()
    debit = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    credit = serializers.DecimalField(max_digits=14, decimal_places=2, allow_null=True)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    account_kind = serializers.CharField(allow_null=True)
    hidden = serializers.BooleanField()


class StatementSerializer(serializers.Serializer):
    opening_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    closing_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    rows = StatementRowSerializer(many=True)
