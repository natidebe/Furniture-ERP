from django.db.models import Q

from .models import DeliveryNote, SalesOrder


def orders_for_user(user):
    """Salespeople see only their own sales (D9); storekeepers the sales their warehouse
    supplies; accountants and admins all."""
    qs = SalesOrder.objects.select_related("customer", "branch", "salesperson", "replaces")
    role = getattr(user, "role", None)
    if role in ("accountant", "admin"):
        return qs
    if role == "salesperson":
        return qs.filter(salesperson=user)
    if role == "storekeeper" and user.home_location_id:
        return qs.filter(Q(lines__source_location=user.home_location_id)
                         | Q(delivery_notes__location=user.home_location_id)).distinct()
    return qs.none()


def delivery_notes_for_user(user):
    return DeliveryNote.objects.filter(order__in=orders_for_user(user)).select_related(
        "order", "location", "issued_by")
