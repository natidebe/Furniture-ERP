from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import ERPPermission
from apps.accounts.permissions import (
    IsAccountantOrAdmin,
    erp_permission,
    role_permission,
)
from apps.catalog.models import Product
from apps.inventory import selectors, services
from apps.inventory.models import (
    GoodsReceipt,
    MovementType,
    StockAdjustment,
    StockBalance,
    StockConditionChange,
    StockMovement,
    StockTransfer,
)
from apps.locations.models import Location

from .serializers import (
    AdjustmentSerializer,
    BalanceSerializer,
    ConditionChangeSerializer,
    DecisionSerializer,
    GoodsReceiptSerializer,
    MovementSerializer,
    ReasonSerializer,
    ReceiveTransferSerializer,
    StockRowSerializer,
    TransferSerializer,
)

IsStockStaff = role_permission("storekeeper", "accountant", "admin")
DEFAULT_RECEIPT_LOCATION = "PAW"


def _lines(validated) -> list[dict]:
    return [{"product": line["product"], "qty": line["qty"],
             **({"condition": line["condition"]} if "condition" in line else {})}
            for line in validated]


def _location_list(locations) -> list[dict]:
    return [{"id": loc.pk, "code": loc.code, "name": loc.name} for loc in locations]


# ---------------------------------------------------------------- balances

class BalanceFilter(filters.FilterSet):
    category = filters.NumberFilter(field_name="product__category")
    low = filters.BooleanFilter(method="filter_low")

    class Meta:
        model = StockBalance
        fields = ["location", "product"]

    def filter_low(self, queryset, name, value):
        if value:
            return queryset.filter(product__in=selectors.low_stock_products())
        return queryset


class StockViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Balances per product and location, with `available = on_hand − reserved`."""

    serializer_class = BalanceSerializer
    filterset_class = BalanceFilter
    search_fields = ["product__code", "product__name"]
    ordering = ["product__code", "location_id"]

    def get_queryset(self):
        return selectors.balances().order_by("product__code", "location_id")

    @extend_schema(responses=inline_serializer("StockSummary", {
        "count": serializers.IntegerField(),
        "next": serializers.CharField(allow_null=True),
        "previous": serializers.CharField(allow_null=True),
        "locations": serializers.ListField(child=serializers.DictField()),
        "results": StockRowSerializer(many=True),
    }))
    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Product × location matrix with In transit and Total (D7). Paginated by product.

        Filters: ?search= (code or name), ?category=, ?low=true.
        """
        products = selectors.products_with_total().filter(is_active=True).order_by("code")
        search = request.query_params.get("search", "").strip()
        if search:
            products = products.filter(Q(code__icontains=search) | Q(name__icontains=search))
        if request.query_params.get("category"):
            products = products.filter(category=request.query_params["category"])
        if request.query_params.get("low") in ("true", "1"):
            products = products.filter(pk__in=selectors.low_stock_products())
        page = self.paginate_queryset(products)
        locations = selectors.matrix_locations()
        rows = StockRowSerializer(selectors.stock_rows(page, locations), many=True).data
        response = self.get_paginated_response(rows)
        response.data["locations"] = _location_list(locations)
        return response


class ProductStockView(APIView):
    """One product across every location — the `VC-001` lookup card."""

    @extend_schema(responses=StockRowSerializer)
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        locations = selectors.matrix_locations()
        row = selectors.stock_rows([product], locations)[0]
        data = StockRowSerializer(row).data
        data["locations"] = _location_list(locations)
        return Response(data)


# ---------------------------------------------------------------- movements

class MovementFilter(filters.FilterSet):
    location = filters.NumberFilter(method="filter_location")
    transaction = filters.CharFilter(field_name="transaction_number", lookup_expr="iexact")
    type = filters.ChoiceFilter(choices=MovementType.choices)
    date_from = filters.DateFilter(field_name="occurred_at", lookup_expr="date__gte")
    date_to = filters.DateFilter(field_name="occurred_at", lookup_expr="date__lte")

    class Meta:
        model = StockMovement
        fields = ["product", "customer", "person"]

    def filter_location(self, queryset, name, value):
        return queryset.filter(Q(from_location=value) | Q(to_location=value))


MovementFilter.base_filters["from"] = MovementFilter.base_filters.pop("date_from")
MovementFilter.base_filters["to"] = MovementFilter.base_filters.pop("date_to")


class MovementViewSet(viewsets.ReadOnlyModelViewSet):
    """Storekeepers see their own location's movements; accountants and admins see all."""

    serializer_class = MovementSerializer
    permission_classes = [IsStockStaff]
    filterset_class = MovementFilter
    search_fields = ["number", "transaction_number", "reference_id", "product__code"]

    def get_queryset(self):
        return selectors.movements_for_user(self.request.user)

    @extend_schema(request=ReasonSerializer, responses={201: MovementSerializer})
    @action(detail=True, methods=["post"],
            permission_classes=[erp_permission(ERPPermission.CORRECT_TRANSACTIONS)])
    def reverse(self, request, pk=None):
        movement = get_object_or_404(StockMovement, pk=pk)
        body = ReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        reversal = services.reverse_movement(movement=movement, person=request.user,
                                             reason=body.validated_data["reason"])
        return Response(MovementSerializer(reversal).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------- goods receipts

class GoodsReceiptViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = GoodsReceiptSerializer
    permission_classes = [IsStockStaff]
    filterset_fields = ["location"]
    search_fields = ["number", "reference"]

    def get_queryset(self):
        qs = GoodsReceipt.objects.select_related("location", "received_by")
        user = self.request.user
        if getattr(user, "role", None) == "storekeeper":
            return qs.filter(location=user.home_location_id)
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        location = data.get("location") or get_object_or_404(Location,
                                                              code=DEFAULT_RECEIPT_LOCATION)
        extra = {"received_at": data["received_at"]} if data.get("received_at") else {}
        serializer.instance = services.receive_goods(
            location=location, lines=_lines(data["lines"]), user=self.request.user,
            reference=data.get("reference", ""), note=data.get("note", ""), **extra)


# ---------------------------------------------------------------- adjustments

class AdjustmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                        mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Storekeepers propose at their own location; `approve_adjustments` decides."""

    serializer_class = AdjustmentSerializer
    permission_classes = [IsStockStaff]
    filterset_fields = ["status", "location", "product", "reason"]
    search_fields = ["number", "product__code"]

    def get_queryset(self):
        qs = StockAdjustment.objects.select_related("location", "product", "movement")
        user = self.request.user
        if getattr(user, "role", None) == "storekeeper":
            return qs.filter(location=user.home_location_id)
        return qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.propose_adjustment(
            location=data["location"], product=data["product"], qty_delta=data["qty_delta"],
            reason=data["reason"], note=data.get("note", ""), user=self.request.user,
            condition=data.get("condition", "new"))

    @extend_schema(request=DecisionSerializer, responses=AdjustmentSerializer)
    @action(detail=True, methods=["post"],
            permission_classes=[erp_permission(ERPPermission.APPROVE_ADJUSTMENTS)])
    def approve(self, request, pk=None):
        body = DecisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        adjustment = services.approve_adjustment(adjustment=self.get_object(),
                                                 user=request.user,
                                                 note=body.validated_data["note"])
        return Response(AdjustmentSerializer(adjustment).data)

    @extend_schema(request=DecisionSerializer, responses=AdjustmentSerializer)
    @action(detail=True, methods=["post"],
            permission_classes=[erp_permission(ERPPermission.APPROVE_ADJUSTMENTS)])
    def reject(self, request, pk=None):
        body = DecisionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        adjustment = services.reject_adjustment(adjustment=self.get_object(),
                                                user=request.user,
                                                note=body.validated_data["note"])
        return Response(AdjustmentSerializer(adjustment).data)


# ---------------------------------------------------------------- transfers

class TransferViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Everyone sees transfers that touch their location; accountants and admins see all.
    Manual transfers (no request) are created by accountants and admins only."""

    serializer_class = TransferSerializer
    filterset_fields = ["status", "from_location", "to_location", "stock_request"]
    search_fields = ["number", "transaction_number"]

    def get_permissions(self):
        if self.action == "create":
            return [IsAccountantOrAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        qs = StockTransfer.objects.select_related("from_location", "to_location")
        user = self.request.user
        if getattr(user, "role", None) in ("accountant", "admin"):
            return qs
        if not getattr(user, "home_location_id", None):
            return qs.none()
        return qs.filter(Q(from_location=user.home_location_id)
                         | Q(to_location=user.home_location_id))

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.create_transfer(
            from_location=data["from_location"], to_location=data["to_location"],
            lines=_lines(data["lines"]), user=self.request.user, note=data.get("note", ""))

    @extend_schema(request=ReceiveTransferSerializer, responses=TransferSerializer)
    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        body = ReceiveTransferSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        received = {line["line_id"]: line["qty"] for line in body.validated_data["lines"]}
        transfer = services.receive_transfer(transfer=self.get_object(), user=request.user,
                                             received=received)
        return Response(TransferSerializer(transfer).data)


class ConditionChangeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                             mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Put pieces on display, mark them damaged, or bring them back to new (D15).
    Staff see and change their own location; accountants and admins all."""

    serializer_class = ConditionChangeSerializer
    filterset_fields = ["product", "location", "from_condition", "to_condition"]
    search_fields = ["number", "product__code"]

    def get_queryset(self):
        qs = StockConditionChange.objects.select_related("product", "location", "person")
        user = self.request.user
        if getattr(user, "role", None) in ("accountant", "admin"):
            return qs
        if not getattr(user, "home_location_id", None):
            return qs.none()
        return qs.filter(location=user.home_location_id)

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = services.change_condition(
            product=data["product"], location=data["location"], qty=data["qty"],
            from_condition=data["from_condition"], to_condition=data["to_condition"],
            reason=data["reason"], user=self.request.user)
