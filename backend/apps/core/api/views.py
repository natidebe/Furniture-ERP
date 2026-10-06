from datetime import date
from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core import ethiopian, services
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


class CalendarView(APIView):
    """Ethiopian ⇄ Gregorian for the web frontend (Q12), so every screen shows the same dates
    as the printouts. ?date=YYYY-MM-DD (Gregorian) or ?ec=YYYY-MM-DD (Ethiopian); default
    today."""

    @extend_schema(parameters=[
        OpenApiParameter("date", str, description="Gregorian YYYY-MM-DD"),
        OpenApiParameter("ec", str, description="Ethiopian YYYY-MM-DD (month 13 = Pagume)")],
        responses=OpenApiResponse(description="Both calendars, plus the Ethiopian month"))
    def get(self, request):
        params = request.query_params
        try:
            if params.get("ec"):
                year, month, day = (int(part) for part in params["ec"].split("-"))
                gregorian = ethiopian.to_gregorian(year, month, day)
            else:
                gregorian = (date.fromisoformat(params["date"]) if params.get("date")
                             else timezone.localdate())
        except ValueError as exc:
            raise ValidationError({"date": str(exc) or "Use YYYY-MM-DD."}) from exc
        ec = ethiopian.to_ethiopian(gregorian)
        first, last = ethiopian.month_range(ec.year, ec.month)
        return Response({
            "gregorian": gregorian.isoformat(),
            "ethiopian": {"year": ec.year, "month": ec.month, "day": ec.day,
                          "month_name": ec.month_name,
                          "month_name_en": ethiopian.MONTHS_EN[ec.month - 1]},
            "display": ethiopian.format_both(gregorian),
            "ethiopian_month": {"first": first.isoformat(), "last": last.isoformat(),
                                "days": ethiopian.month_length(ec.year, ec.month)},
        })
