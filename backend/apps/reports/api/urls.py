from django.urls import path

from .views import DashboardView, ReportView, SearchView, TransactionHistoryView

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("search/", SearchView.as_view(), name="search"),
    path("transactions/<str:number>/", TransactionHistoryView.as_view(),
         name="transaction-history"),
    path("reports/<str:name>/", ReportView.as_view(), name="report"),
]
