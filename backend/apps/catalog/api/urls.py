from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet, ProductViewSet, UnitViewSet

router = SimpleRouter()
router.register("products", ProductViewSet, basename="product")
router.register("categories", CategoryViewSet, basename="category")
router.register("units", UnitViewSet, basename="unit")

urlpatterns = router.urls
