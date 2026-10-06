from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reports.history import transaction_history
from apps.reports.search import search


class SearchView(APIView):
    """Search products, customers, sales, delivery notes, stock requests and payments."""

    @extend_schema(
        parameters=[OpenApiParameter("q", str, required=True),
                    OpenApiParameter("salesperson", int), OpenApiParameter("branch", int),
                    OpenApiParameter("from", str, description="YYYY-MM-DD"),
                    OpenApiParameter("to", str, description="YYYY-MM-DD")],
        responses=OpenApiResponse(description="Grouped results; `exact` = a direct hit"))
    def get(self, request):
        params = request.query_params
        filters = {
            "salesperson": params.get("salesperson") or None,
            "branch": params.get("branch") or None,
            "from": parse_date(params.get("from") or ""),
            "to": parse_date(params.get("to") or ""),
        }
        return Response(search(params.get("q", ""), request.user, filters))


class TransactionHistoryView(APIView):
    """Everything that happened in one transaction, from any of its document numbers."""

    @extend_schema(responses=OpenApiResponse(description="header + events"))
    def get(self, request, number):
        return Response(transaction_history(number, request.user))
