from django.contrib import admin

from apps.inventory.admin import ReadOnlyAdmin, ReadOnlyInline

from .models import DeliveryNote, DeliveryNoteLine, SalesOrder, SalesOrderLine, SalesReturn


class SalesOrderLineInline(ReadOnlyInline):
    model = SalesOrderLine


class DeliveryNoteLineInline(ReadOnlyInline):
    model = DeliveryNoteLine


@admin.register(SalesOrder)
class SalesOrderAdmin(ReadOnlyAdmin):
    """Sales change only through the API's actions; the admin is for looking."""

    list_display = ("number", "created_at", "customer", "branch", "salesperson",
                    "fulfillment_status", "payment_status", "total_amount", "receipt_type")
    list_filter = ("fulfillment_status", "payment_status", "receipt_type", "branch", "channel")
    search_fields = ("number", "customer__name", "customer__phone")
    inlines = [SalesOrderLineInline]


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(ReadOnlyAdmin):
    list_display = ("number", "issued_at", "order", "location", "issued_by")
    search_fields = ("number", "order__number")
    inlines = [DeliveryNoteLineInline]


@admin.register(SalesReturn)
class SalesReturnAdmin(ReadOnlyAdmin):
    list_display = ("number", "created_at", "order", "location", "amount", "created_by")
    search_fields = ("number", "order__number")
