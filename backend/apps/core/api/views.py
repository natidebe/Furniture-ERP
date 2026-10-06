from decimal import Decimal

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import services
from apps.core.models import SystemSettings


class SystemSettingsSerializer(serializers.ModelSerializer):
    max_salesperson_discount_pct = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100"))
    updated_by_name = serializers.CharField(source="updated_by.full_name", default=None,
                                            read_only=True)

    class Meta:
        model = SystemSettings
        fields = ["max_salesperson_discount_pct", "updated_at", "updated_by", "updated_by_name"]
        read_only_fields = ["updated_at", "updated_by"]


class SystemSettingsView(APIView):
    """Everyone reads (the sale screen needs the discount limit); only the admin changes."""

    @extend_schema(responses=SystemSettingsSerializer)
    def get(self, request):
        return Response(SystemSettingsSerializer(services.get_settings()).data)

    @extend_schema(request=SystemSettingsSerializer, responses=SystemSettingsSerializer)
    def patch(self, request):
        body = SystemSettingsSerializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        obj = services.update_settings(user=request.user, **body.validated_data)
        return Response(SystemSettingsSerializer(obj).data)
