from django.urls import path

from .views import SearchView, TransactionHistoryView

urlpatterns = [
    path("search/", SearchView.as_view(), name="search"),
    path("transactions/<str:number>/", TransactionHistoryView.as_view(),
         name="transaction-history"),
]
