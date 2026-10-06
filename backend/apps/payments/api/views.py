from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import ERPPermission
from apps.accounts.permissions import (
    IsAccountantOrAdmin,
    IsAdminOrReadOnly,
    IsSalesStaff,
    erp_permission,
)
from apps.payments import selectors, services
from apps.payments.models import AccountKind, Payment, PaymentAccount, PaymentStatus

from .serializers import (
    AllocateSerializer,
    CorrectPaymentSerializer,
    PaymentAccountSerializer,
    PaymentInputSerializer,
    PaymentOutputSerializer,
    PaymentReasonSerializer,
    payment_dict,
)


def _allocations(validated) -> list[dict]:
    return [{"order": a["order"], "line": a.get("line"), "amount": a["amount"]}
            for a in validated]


class PaymentAccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                            mixins.CreateModelMixin, mixins.UpdateModelMixin,
                            viewsets.GenericViewSet):
    """Admins add accounts (Q8). Salespeople see only the accounts they may use."""

    serializer_class = PaymentAccountSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["kind", "method", "is_active"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if getattr(user, "role", None) == "salesperson":
            return user.allowed_payment_accounts.filter(is_active=True)
        return PaymentAccount.objects.all()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PaymentFilter(filters.FilterSet):
    account_kind = filters.ChoiceFilter(field_name="account__kind", choices=AccountKind.choices)
    status = filters.ChoiceFilter(choices=PaymentStatus.choices)
    order = filters.NumberFilter(field_name="allocations__order", distinct=True)
    salesperson = filters.NumberFilter(method="filter_salesperson")
    branch = filters.NumberFilter(field_name="allocations__order__branch", distinct=True)
    date_from = filters.DateFilter(field_name="paid_at", lookup_expr="date__gte")
    date_to = filters.DateFilter(field_name="paid_at", lookup_expr="date__lte")

    class Meta:
        model = Payment
        fields = ["customer", "account", "number", "receipt_number", "recorded_by"]

    def filter_salesperson(self, queryset, name, value):
        """The order's salesperson; an unallocated payment counts for whoever recorded it."""
        return queryset.filter(Q(allocations__order__salesperson=value)
                               | Q(allocations__isnull=True, recorded_by=value)).distinct()


PaymentFilter.base_filters["from"] = PaymentFilter.base_filters.pop("date_from")
PaymentFilter.base_filters["to"] = PaymentFilter.base_filters.pop("date_to")


class PaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Payments are recorded here and never edited or deleted (D6)."""

    permission_classes = [IsSalesStaff]
    filterset_class = PaymentFilter
    search_fields = ["number", "receipt_number", "customer__name"]
    ordering_fields = ["paid_at", "amount"]
    serializer_class = PaymentOutputSerializer

    def get_queryset(self):
        return selectors.payments_for_user(self.request.user)

    def _one(self, payment, code=status.HTTP_200_OK):
        payment = Payment.objects.select_related("customer", "account", "recorded_by",
                                                 "replaces").get(pk=payment.pk)
        return Response(payment_dict(payment, self.request.user), status=code)

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response([payment_dict(p, request.user) for p in page])

    def retrieve(self, request, *args, **kwargs):
        return self._one(self.get_object())

    @extend_schema(request=PaymentInputSerializer, responses={201: PaymentOutputSerializer})
    def create(self, request, *args, **kwargs):
        body = PaymentInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = dict(body.validated_data)
        payment = services.record_payment(
            customer=data["customer"], account=data["account"], amount=data["amount"],
            method=data["method"], recorded_by=request.user, paid_at=data.get("paid_at"),
            receipt_number=data.get("receipt_number"), note=data["note"],
            allocations=_allocations(data["allocations"]))
        return self._one(payment, status.HTTP_201_CREATED)

    @extend_schema(request=AllocateSerializer, responses=PaymentOutputSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAccountantOrAdmin])
    def allocate(self, request, pk=None):
        body = AllocateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payment = services.allocate_payment(
            payment=self.get_object(), user=request.user,
            allocations=_allocations(body.validated_data["allocations"]))
        return self._one(payment)

    @extend_schema(request=None, responses=PaymentOutputSerializer)
    @action(detail=True, methods=["post"], url_path="allocate-oldest-first",
            permission_classes=[IsAccountantOrAdmin])
    def allocate_oldest_first(self, request, pk=None):
        return self._one(services.allocate_oldest_first(payment=self.get_object(),
                                                        user=request.user))

    @extend_schema(request=None, responses=PaymentOutputSerializer)
    @action(detail=True, methods=["post"],
            permission_classes=[erp_permission(ERPPermission.VERIFY_PAYMENTS)])
    def verify(self, request, pk=None):
        return self._one(services.verify_payment(payment=self._get(pk), user=request.user))

    def _get(self, pk):
        return get_object_or_404(Payment, pk=pk)

    def _with_reason(self, request, pk, service):
        body = PaymentReasonSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._one(service(payment=self._get(pk), user=request.user,
                                 reason=body.validated_data["reason"]))

    @extend_schema(request=PaymentReasonSerializer, responses=PaymentOutputSerializer)
    @action(detail=True, methods=["post"],
            permission_classes=[erp_permission(ERPPermission.VERIFY_PAYMENTS)])
    def reject(self, request, pk=None):
        return self._with_reason(request, pk, services.reject_payment)

    @extend_schema(request=PaymentReasonSerializer, responses=PaymentOutputSerializer)
    @action(detail=True, methods=["post"],
            permission_classes=[erp_permission(ERPPermission.CORRECT_PAYMENTS)])
    def reverse(self, request, pk=None):
        return self._with_reason(request, pk, services.reverse_payment)

    @extend_schema(request=CorrectPaymentSerializer, responses={201: PaymentOutputSerializer})
    @action(detail=True, methods=["post"],
            permission_classes=[erp_permission(ERPPermission.CORRECT_PAYMENTS)])
    def correct(self, request, pk=None):
        body = CorrectPaymentSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = dict(body.validated_data)
        reason = data.pop("reason")
        if "allocations" in data:
            data["allocations"] = _allocations(data["allocations"])
        new = services.correct_payment(payment=self._get(pk), user=request.user,
                                       reason=reason, **data)
        return self._one(new, status.HTTP_201_CREATED)
