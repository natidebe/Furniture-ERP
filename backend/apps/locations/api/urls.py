from rest_framework.routers import SimpleRouter

from .views import LocationViewSet

router = SimpleRouter()
router.register("locations", LocationViewSet, basename="location")

urlpatterns = router.urls
