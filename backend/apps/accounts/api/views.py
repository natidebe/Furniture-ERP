from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts import selectors, services
from apps.accounts.authentication import is_bot_service
from apps.accounts.permissions import IsAdmin

from .serializers import (
    ERPPermissionSerializer,
    LinkCodeSerializer,
    MeSerializer,
    TelegramLinkSerializer,
    UserSerializer,
)


class LoginView(TokenObtainPairView):
    """JWT login. A locked-out account (django-axes) gets
    403 {"code": "account_locked", "detail": ...}, so the login page can tell it apart from
    a wrong password (401)."""

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            if getattr(request, "axes_locked_out", False):
                return Response({"code": "account_locked",
                                 "detail": "Too many failed attempts. Try again in 30 minutes."},
                                status=status.HTTP_403_FORBIDDEN)
            raise


class MeView(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class TelegramLinkCodeView(APIView):
    @extend_schema(request=None, responses={201: LinkCodeSerializer})
    def post(self, request):
        token = services.create_link_code(user=request.user)
        return Response(LinkCodeSerializer(token).data, status=status.HTTP_201_CREATED)


class TelegramLinkView(APIView):
    """Called by the bot only (service token): /start <code> links the sender's Telegram."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(request=TelegramLinkSerializer, responses=MeSerializer)
    def post(self, request):
        if not is_bot_service(request):
            return Response({"code": "not_bot", "detail": "Only the bot can link accounts."},
                            status=status.HTTP_403_FORBIDDEN)
        body = TelegramLinkSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        user = services.link_telegram(code=body.validated_data["code"],
                                      telegram_id=body.validated_data["telegram_id"])
        return Response(MeSerializer(user).data)


class TelegramUnlinkView(APIView):
    """Unlink your own Telegram (e.g. a lost phone)."""

    @extend_schema(request=None, responses=MeSerializer)
    def post(self, request):
        user = services.unlink_telegram(user=request.user, actor=request.user)
        return Response(MeSerializer(user).data)


class ERPPermissionListView(APIView):
    """The permissions an admin can grant per user, and each role's defaults."""

    @extend_schema(responses=ERPPermissionSerializer(many=True))
    def get(self, request):
        return Response(ERPPermissionSerializer.all_permissions())


def _permissions_arg(data: dict) -> dict:
    """The serializer reads/writes `erp_permissions`; services take `permissions`."""
    if "erp_permissions" in data:
        data["permissions"] = data.pop("erp_permissions")
    return data


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                  mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Admin only. Users are deactivated (is_active=false), never deleted."""

    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["role", "home_location", "is_active"]
    search_fields = ["username", "full_name", "phone"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return selectors.staff_users()

    def perform_create(self, serializer):
        serializer.instance = services.create_user(
            actor=self.request.user, **_permissions_arg(dict(serializer.validated_data)))

    def perform_update(self, serializer):
        serializer.instance = services.update_user(
            actor=self.request.user, user=serializer.instance,
            **_permissions_arg(dict(serializer.validated_data)))
