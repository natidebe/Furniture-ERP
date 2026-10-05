from .models import AuditLog


def audit_logs_for_object(obj):
    return AuditLog.objects.filter(model=obj._meta.label, object_id=str(obj.pk))
