from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsAdminOrReadOnly
from apps.catalog import selectors, services
from apps.catalog.models import Category, Unit

from .serializers import (
    CategorySerializer,
    ChangePriceSerializer,
    PriceHistorySerializer,
    ProductSerializer,
    UnitSerializer,
)


class ProductViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                     mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Read for all staff; create, edit and change-price for admins."""

    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["category", "is_active"]
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name", "selling_price"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return selectors.products()

    def perform_create(self, serializer):
        serializer.instance = services.create_product(user=self.request.user,
                                                      **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_product(user=self.request.user,
                                                      product=serializer.instance,
                                                      **serializer.validated_data)

    @extend_schema(request=ChangePriceSerializer, responses=ProductSerializer)
    @action(detail=True, methods=["post"], url_path="change-price",
            permission_classes=[IsAdmin])
    def change_price(self, request, pk=None):
        product = self.get_object()
        serializer = ChangePriceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = services.change_price(product=product, user=request.user,
                                        **serializer.validated_data)
        return Response(ProductSerializer(product).data)

    @extend_schema(responses=PriceHistorySerializer(many=True))
    @action(detail=True, methods=["get"], url_path="price-history")
    def price_history(self, request, pk=None):
        product = self.get_object()
        history = product.price_history.select_related("changed_by")
        return Response(PriceHistorySerializer(history, many=True).data)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    pagination_class = None


class UnitViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    pagination_class = None
