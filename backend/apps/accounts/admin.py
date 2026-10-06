from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import TelegramLinkToken, User


@admin.register(User)
class UserAdmin(SimpleHistoryAdmin, BaseUserAdmin):
    list_display = ("username", "full_name", "role", "home_location", "telegram_id", "is_active")
    list_filter = ("role", "home_location", "is_active")
    search_fields = ("username", "full_name", "phone")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("ERP", {"fields": ("full_name", "phone", "role", "home_location", "telegram_id")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("ERP", {"fields": ("full_name", "phone", "role", "home_location")}),
    )


@admin.register(TelegramLinkToken)
class TelegramLinkTokenAdmin(admin.ModelAdmin):
    list_display = ("token", "user", "created_at", "expires_at", "used_at")
    readonly_fields = ("token", "user", "created_at", "expires_at", "used_at")

    def has_add_permission(self, request):
        return False
