from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts import selectors, services
from apps.accounts.permissions import IsAdmin

from .serializers import (
    ERPPermissionSerializer,
    LinkCodeSerializer,
    MeSerializer,
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
