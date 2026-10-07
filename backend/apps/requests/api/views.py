from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import role_permission
from apps.core.exceptions import BusinessRuleError
from apps.locations.models import Location
from apps.requests import selectors, services
from apps.requests.models import OPEN_STATUSES, RequestStatus, StockRequest

from .serializers import (
    ReleaseSerializer,
    RequestReasonSerializer,
    StockReleaseSerializer,
    StockRequestSerializer,
)

DEFAULT_SOURCE_LOCATION = "PAW"
CanRequestStock = role_permission("salesperson", "admin")
IsStorekeeper = role_permission("storekeeper", "admin")


class StockRequestFilter(filters.FilterSet):
    open = filters.BooleanFilter(
        method="filter_open",
        label="Open requests (pending, acknowledged, partially released), Pending first")

    class Meta:
        model = StockRequest
        fields = ["status", "requesting_location", "source_location", "customer", "salesperson"]

    def filter_open(self, queryset, name, value):
        if not value:
            return queryset.exclude(status__in=OPEN_STATUSES)
        # The storekeeper's work queue (P-30): Pending first, newest first within each.
        return (queryset.filter(status__in=OPEN_STATUSES)
                .annotate(pending_first=Case(When(status=RequestStatus.PENDING, then=Value(0)),
                                             default=Value(1), output_field=IntegerField()))
                .order_by("pending_first", "-created_at"))


class StockRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Salespeople see their branch's requests, storekeepers their warehouse's, accountants
    and admins all. Status changes only through the actions below."""

    serializer_class = StockRequestSerializer
    filterset_class = StockRequestFilter
    search_fields = ["number", "transaction_number", "reference", "customer__name",
                     "lines__product__code"]

    def get_queryset(self):
        return selectors.requests_for_user(self.request.user)

    def get_permissions(self):
        if self.action == "create":
            return [CanRequestStock()]
        if self.action in ("acknowledge", "release", "reject"):
            return [IsStorekeeper()]
        return super().get_permissions()

    def perform_create(self, serializer):
        data = serializer.validated_data
        user = self.request.user
        requesting = data.get("requesting_location") or user.home_location
        if requesting is None:
            raise BusinessRuleError("location_required", "Choose the requesting branch.")
        source = data.get("source_location") or get_object_or_404(
            Location, code=DEFAULT_SOURCE_LOCATION)
        serializer.instance = services.create_stock_request(
            requesting_location=requesting, source_location=source,
            lines=[{"product": line["product"], "qty": line["qty"]} for line in data["lines"]],
            salesperson=user, customer=data.get("customer"),
            reference=data.get("reference", ""), notes=data.get("notes", ""))

    def _respond(self, request_obj):
        return Response(StockRequestSerializer(request_obj).data)

    @extend_schema(request=None, responses=StockRequestSerializer)
    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        return self._respond(services.acknowledge_request(request=self.get_object(),
                                                          user=request.user))

    @extend_schema(request=ReleaseSerializer, responses={201: StockReleaseSerializer})
    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        body = ReleaseSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        release = services.release_stock(
            request=self.get_object(), storekeeper=request.user,
            destination_type=data["destination_type"],
            lines=[{"line_id": line["line_id"], "qty": line["qty"]} for line in data["lines"]],
            note=data["note"])
        return Response(StockReleaseSerializer(release).data, status=status.HTTP_201_CREATED)

    def _with_reason(self, request, service):
        body = RequestReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._respond(service(request=self.get_object(), user=request.user,
                                     reason=body.validated_data["reason"]))

    @extend_schema(request=RequestReasonSerializer, responses=StockRequestSerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._with_reason(request, services.reject_request)

    @extend_schema(request=RequestReasonSerializer, responses=StockRequestSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._with_reason(request, services.cancel_request)

    @extend_schema(request=RequestReasonSerializer, responses=StockRequestSerializer)
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        return self._with_reason(request, services.close_request)
