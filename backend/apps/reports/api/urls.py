from django.urls import path

from .views import ReportView, SearchView, TransactionHistoryView

urlpatterns = [
    path("search/", SearchView.as_view(), name="search"),
    path("transactions/<str:number>/", TransactionHistoryView.as_view(),
         name="transaction-history"),
    path("reports/<str:name>/", ReportView.as_view(), name="report"),
]
