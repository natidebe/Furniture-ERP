from rest_framework import serializers

from apps.customers.models import Customer
from apps.inventory.api.serializers import LineInputSerializer
from apps.locations.models import Location
from apps.requests.models import DestinationType, StockRelease, StockRequest


class StockReleaseSerializer(serializers.ModelSerializer):
    transfer_number = serializers.CharField(source="transfer.number", default=None,
                                            read_only=True)
    transfer_id = serializers.IntegerField(source="transfer.pk", default=None, read_only=True)
    transfer_status = serializers.CharField(source="transfer.status", default=None,
                                            read_only=True)
    released_by_name = serializers.CharField(source="released_by.full_name", read_only=True)
    lines = serializers.SerializerMethodField()

    class Meta:
        model = StockRelease
        fields = ["id", "number", "transaction_number", "destination_type", "transfer_number",
                  "transfer_id", "transfer_status", "released_by", "released_by_name",
                  "released_at", "note", "lines"]

    def get_lines(self, release) -> list[dict]:
        return [{"product": line.product_id, "product_code": line.product.code,
                 "qty": line.qty} for line in release.lines.select_related("product")]


class StockRequestSerializer(serializers.ModelSerializer):
    """Create with `lines` = [{"product": id, "qty": n}]. `requesting_location` defaults to
    your branch, `source_location` to Pawlos."""

    requesting_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), required=False)
    source_location = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), required=False)
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(),
                                                  required=False, allow_null=True)
    lines = LineInputSerializer(many=True, write_only=True)
    salesperson_name = serializers.CharField(source="salesperson.full_name", read_only=True)
    customer_name = serializers.CharField(source="customer.name", default=None, read_only=True)

    class Meta:
        model = StockRequest
        fields = ["id", "number", "transaction_number", "status", "created_at",
                  "requesting_location", "source_location", "customer", "customer_name",
                  "reference", "salesperson", "salesperson_name", "notes", "acknowledged_by",
                  "acknowledged_at", "closed_by", "closed_at", "close_reason", "lines"]
        read_only_fields = ["number", "transaction_number", "status", "created_at",
                            "salesperson", "acknowledged_by", "acknowledged_at", "closed_by",
                            "closed_at", "close_reason"]

    def to_representation(self, request):
        data = super().to_representation(request)
        data["requesting_location_code"] = request.requesting_location.code
        data["source_location_code"] = request.source_location.code
        data["acknowledged_by_name"] = (request.acknowledged_by.full_name
                                        if request.acknowledged_by_id else None)
        data["closed_by_name"] = request.closed_by.full_name if request.closed_by_id else None
        data["lines"] = [
            {"id": line.pk, "product": line.product_id, "product_code": line.product.code,
             "product_name": line.product.name, "qty_requested": line.qty_requested,
             "qty_released": line.qty_released, "qty_remaining": line.qty_remaining}
            for line in request.lines.select_related("product")
        ]
        data["releases"] = StockReleaseSerializer(
            request.releases.select_related("transfer", "released_by"), many=True).data
        return data


class ReleaseLineSerializer(serializers.Serializer):
    line_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=1)


class ReleaseSerializer(serializers.Serializer):
    destination_type = serializers.ChoiceField(choices=DestinationType.choices)
    lines = ReleaseLineSerializer(many=True, allow_empty=False)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class RequestReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)
