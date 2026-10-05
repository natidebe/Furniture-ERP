from rest_framework import serializers

from apps.catalog.models import Product
from apps.inventory.models import (
    AdjustmentReason,
    GoodsReceipt,
    StockAdjustment,
    StockMovement,
    StockTransfer,
)
from apps.locations.models import Location


class LineInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    qty = serializers.IntegerField(min_value=1)


class BalanceSerializer(serializers.Serializer):
    product = serializers.IntegerField(source="product_id")
    product_code = serializers.CharField(source="product.code")
    product_name = serializers.CharField(source="product.name")
    location = serializers.IntegerField(source="location_id")
    location_code = serializers.CharField(source="location.code")
    on_hand = serializers.IntegerField()
    reserved = serializers.IntegerField()
    available = serializers.IntegerField()


class LocationStockSerializer(serializers.Serializer):
    on_hand = serializers.IntegerField()
    reserved = serializers.IntegerField()
    available = serializers.IntegerField()


class StockRowSerializer(serializers.Serializer):
    product = serializers.IntegerField(source="product.pk")
    code = serializers.CharField(source="product.code")
    name = serializers.CharField(source="product.name")
    selling_price = serializers.DecimalField(source="product.selling_price", max_digits=14,
                                             decimal_places=2)
    min_stock = serializers.IntegerField(source="product.min_stock")
    stock = serializers.DictField(child=LocationStockSerializer())
    in_transit = serializers.IntegerField()
    total = serializers.IntegerField()
    low_stock = serializers.SerializerMethodField()

    def get_low_stock(self, row) -> bool:
        return 0 < row["product"].min_stock and row["total"] < row["product"].min_stock


class MovementSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    from_location_code = serializers.CharField(source="from_location.code", default=None,
                                               read_only=True)
    to_location_code = serializers.CharField(source="to_location.code", default=None,
                                             read_only=True)
    customer_name = serializers.CharField(source="customer.name", default=None, read_only=True)
    person_name = serializers.CharField(source="person.full_name", read_only=True)
    reverses_number = serializers.CharField(source="reverses.number", default=None,
                                            read_only=True)

    class Meta:
        model = StockMovement
        fields = ["id", "number", "occurred_at", "type", "product", "product_code",
                  "product_name", "qty", "from_location", "from_location_code", "to_location",
                  "to_location_code", "customer", "customer_name", "person", "person_name",
                  "reference_type", "reference_id", "transaction_number", "note",
                  "reverses_number"]
        read_only_fields = fields


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class GoodsReceiptSerializer(serializers.ModelSerializer):
    """`location` defaults to Pawlos. `lines` = [{"product": id, "qty": n}]."""

    location = serializers.PrimaryKeyRelatedField(queryset=Location.objects.all(),
                                                  required=False)
    lines = LineInputSerializer(many=True, write_only=True)

    class Meta:
        model = GoodsReceipt
        fields = ["id", "number", "location", "reference", "received_at", "received_by",
                  "note", "lines"]
        read_only_fields = ["number", "received_by"]

    def to_representation(self, receipt):
        data = super().to_representation(receipt)
        data["lines"] = [{"product": line.product_id, "product_code": line.product.code,
                          "qty": line.qty} for line in receipt.lines.select_related("product")]
        return data


class AdjustmentSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source="product.code", read_only=True)
    location_code = serializers.CharField(source="location.code", read_only=True)
    movement_number = serializers.CharField(source="movement.number", default=None,
                                            read_only=True)
    reason = serializers.ChoiceField(choices=AdjustmentReason.choices)

    class Meta:
        model = StockAdjustment
        fields = ["id", "number", "location", "location_code", "product", "product_code",
                  "qty_delta", "reason", "note", "status", "proposed_by", "proposed_at",
                  "decided_by", "decided_at", "decision_note", "movement_number"]
        read_only_fields = ["number", "status", "proposed_by", "proposed_at", "decided_by",
                            "decided_at", "decision_note"]


class DecisionSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class TransferSerializer(serializers.ModelSerializer):
    from_location_code = serializers.CharField(source="from_location.code", read_only=True)
    to_location_code = serializers.CharField(source="to_location.code", read_only=True)
    lines = LineInputSerializer(many=True, write_only=True)

    class Meta:
        model = StockTransfer
        fields = ["id", "number", "from_location", "from_location_code", "to_location",
                  "to_location_code", "status", "transaction_number", "stock_request",
                  "sent_by", "sent_at", "received_by", "received_at", "discrepancy_note",
                  "note", "lines"]
        read_only_fields = ["number", "status", "transaction_number", "stock_request",
                            "sent_by", "sent_at", "received_by", "received_at",
                            "discrepancy_note"]

    def to_representation(self, transfer):
        data = super().to_representation(transfer)
        data["lines"] = [{"id": line.pk, "product": line.product_id,
                          "product_code": line.product.code, "qty_sent": line.qty_sent,
                          "qty_received": line.qty_received}
                         for line in transfer.lines.select_related("product")]
        return data


class ReceiveLineSerializer(serializers.Serializer):
    line_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=0)


class ReceiveTransferSerializer(serializers.Serializer):
    """Omit `lines` (or a line) to receive everything that was sent."""

    lines = ReceiveLineSerializer(many=True, required=False, default=list)
