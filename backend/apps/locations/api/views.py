from rest_framework import mixins, viewsets

from apps.accounts.permissions import IsAdminOrReadOnly
from apps.locations import services
from apps.locations.models import Location

from .serializers import LocationSerializer


class LocationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Read for all staff; create and edit for admins. Deactivate instead of deleting."""

    queryset = Location.objects.select_related("parent")
    serializer_class = LocationSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["type", "can_sell", "can_release", "is_active"]
    search_fields = ["code", "name"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.instance = services.create_location(user=self.request.user,
                                                       **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_location(user=self.request.user,
                                                       location=serializer.instance,
                                                       **serializer.validated_data)
