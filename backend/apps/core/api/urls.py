from django.urls import path

from .views import CalendarView, SystemSettingsView

urlpatterns = [
    path("settings/", SystemSettingsView.as_view(), name="settings"),
    path("calendar/", CalendarView.as_view(), name="calendar"),
]
