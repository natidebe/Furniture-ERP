from django.contrib import admin

from .models import DocumentSequence


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ("prefix", "year", "last_number")
    list_filter = ("year",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
