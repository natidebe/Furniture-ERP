from django.urls import path

from .views import SystemSettingsView

urlpatterns = [
    path("settings/", SystemSettingsView.as_view(), name="settings"),
]
