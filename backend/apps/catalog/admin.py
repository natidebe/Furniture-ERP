from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Category, PriceHistory, Product, Unit


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol")


@admin.register(Product)
class ProductAdmin(SimpleHistoryAdmin):
    list_display = ("code", "name", "category", "unit", "selling_price", "min_stock", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name")
    # Prices change through the change-price endpoint so PriceHistory and the audit log
    # are always written.
    readonly_fields = ("selling_price",)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields if obj else ()


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "old_price", "new_price", "changed_by", "changed_at", "reason")
    search_fields = ("product__code", "product__name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
