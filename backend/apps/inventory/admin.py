from django.contrib import admin

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    StockAdjustment,
    StockBalance,
    StockConditionChange,
    StockMovement,
    StockTransfer,
    StockTransferLine,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Stock changes only through inventory.services; the admin is for looking."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyInline(admin.TabularInline):
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(ReadOnlyAdmin):
    list_display = ("number", "occurred_at", "type", "product", "qty", "from_location",
                    "to_location", "transaction_number", "person")
    list_filter = ("type", "from_location", "to_location")
    search_fields = ("number", "transaction_number", "reference_id", "product__code")
    date_hierarchy = "occurred_at"


@admin.register(StockBalance)
class StockBalanceAdmin(ReadOnlyAdmin):
    list_display = ("product", "location", "on_hand", "reserved", "display", "damaged",
                    "updated_at")
    list_filter = ("location",)
    search_fields = ("product__code", "product__name")


class GoodsReceiptLineInline(ReadOnlyInline):
    model = GoodsReceiptLine


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(ReadOnlyAdmin):
    list_display = ("number", "received_at", "location", "reference", "received_by")
    search_fields = ("number", "reference")
    inlines = [GoodsReceiptLineInline]


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(ReadOnlyAdmin):
    list_display = ("number", "proposed_at", "location", "product", "qty_delta", "reason",
                    "status", "proposed_by", "decided_by")
    list_filter = ("status", "reason", "location")
    search_fields = ("number", "product__code")


class StockTransferLineInline(ReadOnlyInline):
    model = StockTransferLine


@admin.register(StockTransfer)
class StockTransferAdmin(ReadOnlyAdmin):
    list_display = ("number", "sent_at", "from_location", "to_location", "status",
                    "transaction_number", "has_discrepancy")
    list_filter = ("status", "from_location", "to_location")
    search_fields = ("number", "transaction_number")
    inlines = [StockTransferLineInline]

    @admin.display(boolean=True)
    def has_discrepancy(self, obj):
        return obj.has_discrepancy


@admin.register(StockConditionChange)
class StockConditionChangeAdmin(ReadOnlyAdmin):
    list_display = ("number", "occurred_at", "product", "location", "qty", "from_condition",
                    "to_condition", "person")
    list_filter = ("location", "from_condition", "to_condition")
    search_fields = ("number", "product__code")
