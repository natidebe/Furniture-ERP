from django.http import HttpResponse
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reports import excel, selectors
from apps.reports.dashboard import dashboard
from apps.reports.history import transaction_history
from apps.reports.search import search

# Which reports each role may run (BUILD_PHASES.md 4.3).
ROLE_REPORTS = {
    "salesperson": {"sales"},
    "storekeeper": {"stock", "movements", "open-requests"},
    "accountant": set(excel.BUILDERS),
    "admin": set(excel.BUILDERS),
}
DATED = {"sales", "payments", "credit", "movements"}
FILTERS = ("branch", "salesperson", "customer", "order", "account", "category", "product",
           "location")


class DashboardView(APIView):
    """The home page for the signed-in user's role in one call (P-02)."""

    @extend_schema(responses=OpenApiResponse(
        description="role, then one block per tile: {count, items[]} (see reports/dashboard.py)"))
    def get(self, request):
        return Response(dashboard(request.user))


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


def _calendar(params) -> str:
    calendar = params.get("calendar") or "ethiopian"
    if calendar not in selectors.CALENDARS:
        raise ValidationError({"calendar": "ethiopian or gregorian."})
    return calendar


def _range(params):
    """?from=&to= wins; otherwise ?period=day|week|month|year&date= (default: today);
    months and years are Ethiopian unless ?calendar=gregorian (Q12)."""
    first, last = parse_date(params.get("from") or ""), parse_date(params.get("to") or "")
    if first or last:
        if not (first and last) or first > last:
            raise ValidationError({"from": "Give both from and to, from ≤ to (YYYY-MM-DD)."})
        return first, last
    period = params.get("period") or "day"
    if period not in selectors.PERIODS:
        raise ValidationError({"period": f"One of {', '.join(selectors.PERIODS)}."})
    return selectors.period_range(period, parse_date(params.get("date") or ""),
                                  _calendar(params))


class ReportView(APIView):
    """GET /reports/{name}/ — JSON, or Excel with ?format=xlsx (needs export_reports).
    Dated reports take ?period=day|week|month|year&date=YYYY-MM-DD or ?from=&to=."""

    @extend_schema(
        parameters=[
            OpenApiParameter("period", str, enum=list(selectors.PERIODS)),
            OpenApiParameter("date", str, description="YYYY-MM-DD, inside the period"),
            OpenApiParameter("calendar", str, enum=["ethiopian", "gregorian"],
                             description="Months and years (default ethiopian)"),
            OpenApiParameter("from", str), OpenApiParameter("to", str),
            OpenApiParameter("format", str, enum=["json", "xlsx"]),
            OpenApiParameter("group_by", str, enum=list(selectors.PERIODS),
                             description="payments: one row per day / week / month / year"),
            *[OpenApiParameter(f, int) for f in FILTERS],
            OpenApiParameter("account_kind", str, enum=["organization", "personal"]),
            OpenApiParameter("type", str, description="movements: movement type")],
        responses=OpenApiResponse(description="Report data, or an .xlsx file"))
    def get(self, request, name):
        if name not in excel.BUILDERS:
            raise NotFound("No such report.")
        user = request.user
        if name not in ROLE_REPORTS.get(user.role, set()):
            raise PermissionDenied("You cannot run this report.")
        params = request.query_params
        wants_excel = params.get("format") == "xlsx"
        if wants_excel and not user.has_erp_permission("export_reports"):
            raise PermissionDenied("You are not allowed to export reports.")
        filters = {f: params.get(f) for f in FILTERS if params.get(f)}
        for f in ("account_kind", "type"):
            if params.get(f):
                filters[f] = params[f]
        if user.role == "storekeeper":
            filters["location"] = user.home_location_id

        if name in DATED:
            first, last = _range(params)
            if name == "payments":
                group_by = params.get("group_by") or "day"
                if group_by not in selectors.PERIODS:
                    raise ValidationError({"group_by": "day, week, month or year."})
                data = selectors.payments_report(user, first, last, filters, group_by,
                                                 _calendar(params))
            elif name == "sales":
                data = selectors.sales_report(user, first, last, filters, _calendar(params))
            else:
                report = {"credit": selectors.credit_report,
                          "movements": selectors.movements_report}[name]
                data = report(user, first, last, filters)
        else:
            report = {"stock": selectors.stock_report,
                      "open-requests": selectors.open_requests_report,
                      "unverified-payments": selectors.unverified_payments_report}[name]
            data = report(user, filters)

        if wants_excel:
            response = HttpResponse(
                excel.workbook_bytes(name, data),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="{excel.filename(name, data)}"'
            return response
        return Response(data)
