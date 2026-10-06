from rest_framework.routers import SimpleRouter

from .views import AuditLogViewSet

router = SimpleRouter()
router.register("audit", AuditLogViewSet, basename="audit")

urlpatterns = router.urls
