from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import health

api_v1 = [
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.locations.api.urls")),
    path("", include("apps.catalog.api.urls")),
    path("", include("apps.inventory.api.urls")),
    path("", include("apps.requests.api.urls")),
    path("", include("apps.customers.api.urls")),
    path("", include("apps.sales.api.urls")),
    path("", include("apps.payments.api.urls")),
    path("", include("apps.reports.api.urls")),
    path("", include("apps.core.api.urls")),
    path("", include("apps.audit.api.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"),
         name="swagger-ui"),
]
