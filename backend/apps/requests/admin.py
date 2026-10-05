from django.contrib import admin

from apps.inventory.admin import ReadOnlyAdmin, ReadOnlyInline

from .models import StockRelease, StockReleaseLine, StockRequest, StockRequestLine


class StockRequestLineInline(ReadOnlyInline):
    model = StockRequestLine


class StockReleaseLineInline(ReadOnlyInline):
    model = StockReleaseLine


@admin.register(StockRequest)
class StockRequestAdmin(ReadOnlyAdmin):
    list_display = ("number", "created_at", "requesting_location", "source_location",
                    "customer", "salesperson", "status")
    list_filter = ("status", "requesting_location", "source_location")
    search_fields = ("number", "transaction_number", "reference", "customer__name")
    inlines = [StockRequestLineInline]


@admin.register(StockRelease)
class StockReleaseAdmin(ReadOnlyAdmin):
    list_display = ("number", "released_at", "request", "destination_type", "released_by")
    search_fields = ("number", "transaction_number")
    inlines = [StockReleaseLineInline]
