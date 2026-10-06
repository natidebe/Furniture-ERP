from rest_framework.routers import SimpleRouter

from .views import PaymentAccountViewSet, PaymentViewSet

router = SimpleRouter()
router.register("payment-accounts", PaymentAccountViewSet, basename="payment-account")
router.register("payments", PaymentViewSet, basename="payment")

urlpatterns = router.urls
