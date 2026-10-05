from django_filters import rest_framework as filters
from rest_framework import viewsets

from apps.accounts.permissions import IsAccountantOrAdmin
from apps.audit.models import AuditLog

from .serializers import AuditLogSerializer


class AuditLogFilter(filters.FilterSet):
    date_from = filters.DateFilter(field_name="at", lookup_expr="date__gte")
    date_to = filters.DateFilter(field_name="at", lookup_expr="date__lte")

    class Meta:
        model = AuditLog
        fields = ["model", "object_id", "actor", "action", "source"]


# The API uses ?from= and ?to=, which can't be Python attribute names.
AuditLogFilter.base_filters["from"] = AuditLogFilter.base_filters.pop("date_from")
AuditLogFilter.base_filters["to"] = AuditLogFilter.base_filters.pop("date_to")


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditLog.objects.select_related("actor")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAccountantOrAdmin]
    filterset_class = AuditLogFilter
    ordering_fields = ["at"]
