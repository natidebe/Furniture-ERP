from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Location


@admin.register(Location)
class LocationAdmin(SimpleHistoryAdmin):
    list_display = ("code", "name", "type", "parent", "can_sell", "can_release", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("code", "name")
