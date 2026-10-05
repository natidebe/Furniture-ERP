from .models import StockRequest


def requests_for_user(user):
    """Salespeople: their branch's requests. Storekeepers: their warehouse's.
    Accountants and admins: all."""
    qs = (StockRequest.objects
          .select_related("requesting_location", "source_location", "customer", "salesperson")
          .distinct())
    role = getattr(user, "role", None)
    if role in ("accountant", "admin"):
        return qs
    if not getattr(user, "home_location_id", None):
        return qs.none()
    if role == "salesperson":
        return qs.filter(requesting_location=user.home_location_id)
    if role == "storekeeper":
        return qs.filter(source_location=user.home_location_id)
    return qs.none()
