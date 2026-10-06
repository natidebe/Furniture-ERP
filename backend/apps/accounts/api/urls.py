from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ERPPermissionListView,
    LoginView,
    MeView,
    TelegramLinkCodeView,
    TelegramLinkView,
    TelegramUnlinkView,
    UserViewSet,
)

router = SimpleRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/token/", LoginView.as_view(), name="token-obtain"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/telegram/link-code/", TelegramLinkCodeView.as_view(), name="telegram-link-code"),
    path("auth/telegram/link/", TelegramLinkView.as_view(), name="telegram-link"),
    path("auth/telegram/unlink/", TelegramUnlinkView.as_view(), name="telegram-unlink"),
    path("permissions/", ERPPermissionListView.as_view(), name="erp-permissions"),
    *router.urls,
]
