from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", default=None, read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "at", "actor", "actor_name", "action", "model", "object_id",
                  "before", "after", "reason", "source", "ip"]
        read_only_fields = fields
