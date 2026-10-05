from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import selectors, services
from apps.accounts.permissions import IsAdmin

from .serializers import LinkCodeSerializer, MeSerializer, UserSerializer


class MeView(APIView):
    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class TelegramLinkCodeView(APIView):
    @extend_schema(request=None, responses={201: LinkCodeSerializer})
    def post(self, request):
        token = services.create_link_code(user=request.user)
        return Response(LinkCodeSerializer(token).data, status=status.HTTP_201_CREATED)


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
        serializer.instance = services.create_user(actor=self.request.user,
                                                   **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_user(actor=self.request.user,
                                                   user=serializer.instance,
                                                   **serializer.validated_data)
