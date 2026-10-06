from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AdjustmentViewSet,
    ConditionChangeViewSet,
    GoodsReceiptViewSet,
    MovementViewSet,
    ProductStockView,
    StockViewSet,
    TransferViewSet,
)

router = SimpleRouter()
# stock/movements before stock, so "stock/movements/" is never read as a balance id.
router.register("stock/movements", MovementViewSet, basename="movement")
router.register("stock/condition-changes", ConditionChangeViewSet, basename="condition-change")
router.register("stock", StockViewSet, basename="stock")
router.register("goods-receipts", GoodsReceiptViewSet, basename="goods-receipt")
router.register("adjustments", AdjustmentViewSet, basename="adjustment")
router.register("transfers", TransferViewSet, basename="transfer")

urlpatterns = [
    path("products/<int:pk>/stock/", ProductStockView.as_view(), name="product-stock"),
    *router.urls,
]
