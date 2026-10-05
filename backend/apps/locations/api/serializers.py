from rest_framework import serializers

from apps.locations.models import Location


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "code", "name", "type", "parent", "can_sell", "can_release", "is_active"]

    def validate_code(self, value):
        value = value.strip().upper()
        clash = Location.objects.filter(code=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("A location with this code already exists.")
        return value

    def validate_parent(self, value):
        if value is not None and self.instance is not None and value.pk == self.instance.pk:
            raise serializers.ValidationError("A location cannot be its own parent.")
        return value
