from rest_framework.routers import SimpleRouter

from .views import StockRequestViewSet

router = SimpleRouter()
router.register("stock-requests", StockRequestViewSet, basename="stock-request")

urlpatterns = router.urls
