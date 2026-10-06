from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.inventory.admin import ReadOnlyAdmin, ReadOnlyInline

from .models import Payment, PaymentAccount, PaymentAllocation


@admin.register(PaymentAccount)
class PaymentAccountAdmin(SimpleHistoryAdmin):
    list_display = ("name", "kind", "method", "bank_name", "account_number", "is_active")
    list_filter = ("kind", "method", "is_active")

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentAllocationInline(ReadOnlyInline):
    model = PaymentAllocation


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdmin):
    """Payments change only through the API (verify, reject, reverse, correct)."""

    list_display = ("number", "paid_at", "customer", "amount", "account", "receipt_number",
                    "status", "recorded_by")
    list_filter = ("status", "account__kind", "account")
    search_fields = ("number", "receipt_number", "customer__name")
    inlines = [PaymentAllocationInline]
