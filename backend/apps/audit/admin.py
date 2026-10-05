from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only: the audit log can't be added to, changed or deleted from the admin."""

    list_display = ("at", "actor", "action", "model", "object_id", "source", "ip")
    list_filter = ("action", "model", "source")
    search_fields = ("object_id", "reason", "actor__username")
    date_hierarchy = "at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
