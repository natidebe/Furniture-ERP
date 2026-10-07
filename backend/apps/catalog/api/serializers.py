from decimal import Decimal

from rest_framework import serializers

from apps.catalog.models import Category, PriceHistory, PriceType, Product, Unit


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent", "is_active"]


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ["id", "name", "symbol"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    unit_symbol = serializers.CharField(source="unit.symbol", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "code", "name", "category", "category_name", "unit", "unit_symbol",
                  "selling_price", "wholesale_price", "min_stock", "description", "is_active",
                  "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        # Prices are set on create; afterwards they change only through change-price.
        if self.instance is not None:
            fields["selling_price"].read_only = True
            fields["wholesale_price"].read_only = True
        return fields

    def validate_code(self, value):
        value = value.strip().upper()
        clash = Product.objects.filter(code=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("A product with this code already exists.")
        return value


class ChangePriceSerializer(serializers.Serializer):
    price_type = serializers.ChoiceField(choices=PriceType.choices, default=PriceType.SELLING)
    new_price = serializers.DecimalField(max_digits=14, decimal_places=2,
                                         min_value=Decimal("0.01"))
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class PriceHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", default=None,
                                            read_only=True)

    class Meta:
        model = PriceHistory
        fields = ["id", "price_type", "old_price", "new_price", "changed_by", "changed_by_name",
                  "changed_at", "reason"]


MAX_IMPORT_BYTES = 5 * 1024 * 1024


class ImportProductsSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="The filled .xlsx template")
    dry_run = serializers.BooleanField(default=False,
                                       help_text="Check only: report what would change")

    def validate_file(self, value):
        if not value.name.lower().endswith(".xlsx"):
            raise serializers.ValidationError("Upload an .xlsx file.")
        if value.size > MAX_IMPORT_BYTES:
            raise serializers.ValidationError("The file is larger than 5 MB.")
        return value
