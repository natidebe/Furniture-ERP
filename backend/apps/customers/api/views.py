from django.utils.dateparse import parse_date
from django_filters import rest_framework as filters
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsSalesStaff
from apps.customers import selectors, services
from apps.customers.models import Customer

from .serializers import CustomerBalanceSerializer, CustomerSerializer, StatementSerializer


class CustomerFilter(filters.FilterSet):
    has_balance = filters.BooleanFilter(method="filter_has_balance",
                                        label="Owes money (outstanding > 0)")
    over_limit = filters.BooleanFilter(field_name="over_limit",
                                       label="Owes without credit, or above their limit")

    class Meta:
        model = Customer
        fields = ["type", "city", "credit_allowed", "is_active"]

    def filter_has_balance(self, queryset, name, value):
        return queryset.filter(outstanding__gt=0) if value else queryset.filter(outstanding=0)


class CustomerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                      mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Sales staff (salespeople, accountants, admins) see and create customers. Credit terms
    change only with approve_credit. Customers are deactivated, never deleted."""

    serializer_class = CustomerSerializer
    permission_classes = [IsSalesStaff]
    filterset_class = CustomerFilter
    search_fields = ["name", "phone", "shop_name"]
    ordering_fields = ["name", "created_at", "outstanding"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return selectors.customers_with_balance()

    def _with_warnings(self, response, customer):
        others = selectors.phone_used_by_others(customer.phone, exclude_pk=customer.pk)
        if others:  # a warning, not a block: resellers may share a number
            response.data["warnings"] = [
                f"Phone {customer.phone} is also used by "
                + ", ".join(c.name for c in others) + "."]
        return response

    def perform_create(self, serializer):
        customer = services.create_customer(user=self.request.user,
                                            **serializer.validated_data)
        serializer.instance = self.get_queryset().get(pk=customer.pk)

    def perform_update(self, serializer):
        customer = services.update_customer(user=self.request.user,
                                            customer=serializer.instance,
                                            **serializer.validated_data)
        serializer.instance = self.get_queryset().get(pk=customer.pk)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return self._with_warnings(response, Customer.objects.get(pk=response.data["id"]))

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        return self._with_warnings(response, self.get_object())

    @extend_schema(responses=CustomerBalanceSerializer)
    @action(detail=True, methods=["get"])
    def balance(self, request, pk=None):
        balance = selectors.customer_balance(self.get_object())
        return Response(CustomerBalanceSerializer(balance).data)

    @extend_schema(responses=StatementSerializer, parameters=[
        OpenApiParameter("from", str, description="YYYY-MM-DD"),
        OpenApiParameter("to", str, description="YYYY-MM-DD")])
    @action(detail=True, methods=["get"])
    def statement(self, request, pk=None):
        statement = selectors.customer_statement(
            self.get_object(), request.user,
            date_from=parse_date(request.query_params.get("from") or ""),
            date_to=parse_date(request.query_params.get("to") or ""))
        return Response(StatementSerializer(statement).data)
