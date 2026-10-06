from rest_framework.routers import SimpleRouter

from .views import DeliveryNoteViewSet, OrderViewSet

router = SimpleRouter()
router.register("orders", OrderViewSet, basename="order")
router.register("delivery-notes", DeliveryNoteViewSet, basename="delivery-note")

urlpatterns = router.urls
