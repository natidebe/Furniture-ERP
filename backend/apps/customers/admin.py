from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(SimpleHistoryAdmin):
    list_display = ("name", "shop_name", "phone", "city", "type", "credit_allowed",
                    "credit_limit", "is_active")
    list_filter = ("type", "credit_allowed", "is_active")
    search_fields = ("name", "shop_name", "phone")
