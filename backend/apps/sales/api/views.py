from django.http import HttpResponse
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsSalesStaff, role_permission
from apps.core.exceptions import BusinessRuleError
from apps.sales import selectors, services
from apps.sales.models import FulfillmentStatus, OrderPaymentStatus, SalesOrder

from .serializers import (
    DeliveryNoteSerializer,
    LinesSerializer,
    OrderCreateSerializer,
    OrderOutputSerializer,
    OrderReasonSerializer,
    OrderUpdateSerializer,
    ReturnSerializer,
    StatusSerializer,
    order_dict,
    order_payments_dict,
)

CanSeeOrders = role_permission("salesperson", "storekeeper", "accountant", "admin")


def _lines(validated) -> list[dict]:
    lines = []
    for line in validated:
        item = {"product": line["product"], "qty": line["qty"], "discount": line["discount"]}
        if line.get("source_location") is not None:
            item["source_location"] = line["source_location"]
        lines.append(item)
    return lines


class OrderFilter(filters.FilterSet):
    status = filters.ChoiceFilter(field_name="fulfillment_status",
                                  choices=FulfillmentStatus.choices)
    payment_status = filters.ChoiceFilter(choices=OrderPaymentStatus.choices)
    number = filters.CharFilter(lookup_expr="iexact")
    date_from = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = SalesOrder
        fields = ["customer", "branch", "salesperson", "channel", "receipt_type"]


OrderFilter.base_filters["from"] = OrderFilter.base_filters.pop("date_from")
OrderFilter.base_filters["to"] = OrderFilter.base_filters.pop("date_to")


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Sales. Every state change is an action below; nothing is deleted (D6)."""

    permission_classes = [CanSeeOrders]
    filterset_class = OrderFilter
    search_fields = ["number", "customer__name", "customer__phone"]
    ordering_fields = ["created_at", "confirmed_at", "total_amount"]
    serializer_class = OrderOutputSerializer

    def get_queryset(self):
        return selectors.orders_for_user(self.request.user)

    def _one(self, order, code=status.HTTP_200_OK):
        order = SalesOrder.objects.select_related("customer", "branch", "salesperson",
                                                  "replaces").get(pk=order.pk)
        return Response(order_dict(order, self.request.user), status=code)

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response([order_dict(o, request.user, detail=False)
                                            for o in page])

    def retrieve(self, request, *args, **kwargs):
        return self._one(self.get_object())

    @extend_schema(request=OrderCreateSerializer, responses={201: OrderOutputSerializer})
    def create(self, request, *args, **kwargs):
        if not IsSalesStaff().has_permission(request, self):
            return Response({"detail": "Only sales staff create sales."},
                            status=status.HTTP_403_FORBIDDEN)
        body = OrderCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        branch = data.get("branch") or request.user.home_location
        if branch is None:
            raise BusinessRuleError("location_required", "Choose the branch.")
        payment = dict(data["payment"]) if data.get("payment") else None
        order = services.create_order(
            customer=data["customer"], branch=branch, lines=_lines(data["lines"]),
            user=request.user, channel=data["channel"], receipt_type=data["receipt_type"],
            notes=data["notes"], payment=payment, replaces=data.get("replaces"))
        return self._one(order, status.HTTP_201_CREATED)

    @extend_schema(request=OrderUpdateSerializer, responses=OrderOutputSerializer)
    def partial_update(self, request, *args, **kwargs):
        body = OrderUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = dict(body.validated_data)
        if "lines" in data:
            data["lines"] = _lines(data["lines"])
        order = services.update_draft_order(order=self.get_object(), user=request.user, **data)
        return self._one(order)

    @extend_schema(request=None, responses=OrderOutputSerializer)
    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._one(services.confirm_order(order=self.get_object(), user=request.user))

    @extend_schema(request=LinesSerializer, responses=OrderOutputSerializer)
    @action(detail=True, methods=["post"], url_path="release-from-branch")
    def release_from_branch(self, request, pk=None):
        body = LinesSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        order = self.get_object()
        services.release_from_branch(order=order, user=request.user,
                                     lines=body.validated_data["lines"])
        return self._one(order)

    @extend_schema(request=LinesSerializer, responses=OrderOutputSerializer)
    @action(detail=True, methods=["post"], url_path="request-stock")
    def request_stock(self, request, pk=None):
        body = LinesSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        order = self.get_object()
        services.request_stock_for_order(order=order, user=request.user,
                                         lines=body.validated_data["lines"])
        return self._one(order)

    @extend_schema(request=StatusSerializer, responses=OrderOutputSerializer)
    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, pk=None):
        body = StatusSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._one(services.mark_prepared(order=self.get_object(), user=request.user))

    def _with_reason(self, request, service):
        body = OrderReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._one(service(order=self.get_object(), user=request.user,
                                 reason=body.validated_data["reason"]))

    @extend_schema(request=OrderReasonSerializer, responses=OrderOutputSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._with_reason(request, services.cancel_order)

    @extend_schema(request=OrderReasonSerializer, responses=OrderOutputSerializer)
    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        return self._with_reason(request, services.void_order)

    @extend_schema(request=ReturnSerializer, responses=OrderOutputSerializer)
    @action(detail=True, methods=["post"], url_path="return")
    def return_goods(self, request, pk=None):
        body = ReturnSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        order = self.get_object()
        services.return_goods(order=order, user=request.user, location=data["location"],
                              reason=data["reason"], lines=data["lines"])
        return self._one(order)

    @extend_schema(responses=OpenApiResponse(description="Order payments and their history"))
    @action(detail=True, methods=["get"])
    def payments(self, request, pk=None):
        return Response(order_payments_dict(self.get_object(), request.user))

    @extend_schema(responses=OpenApiResponse(description="The transaction history"))
    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        from apps.reports.history import transaction_history

        return Response(transaction_history(self.get_object().number, request.user))


class DeliveryNoteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DeliveryNoteSerializer
    permission_classes = [CanSeeOrders]
    filterset_fields = ["order", "location"]
    search_fields = ["number", "order__number"]

    def get_queryset(self):
        return selectors.delivery_notes_for_user(self.request.user)

    @extend_schema(responses={(200, "application/pdf"): OpenApiResponse(description="PDF")})
    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        from apps.sales.pdf import delivery_note_pdf

        note = self.get_object()
        response = HttpResponse(delivery_note_pdf(note), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{note.number}.pdf"'
        return response
