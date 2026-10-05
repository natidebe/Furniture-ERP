from django.db import transaction

from apps.audit.services import audit_log

from .models import Location

_AUDITED_FIELDS = ("code", "name", "type", "parent_id", "can_sell", "can_release", "is_active")


def _snapshot(location: Location) -> dict:
    return {field: getattr(location, field) for field in _AUDITED_FIELDS}


@transaction.atomic
def create_location(*, user, **fields) -> Location:
    location = Location.objects.create(created_by=user, **fields)
    audit_log(actor=user, action="location_created", obj=location, after=_snapshot(location))
    return location


@transaction.atomic
def update_location(*, user, location: Location, **fields) -> Location:
    location = Location.objects.select_for_update().get(pk=location.pk)
    before = _snapshot(location)
    for name, value in fields.items():
        setattr(location, name, value)
    location.save()
    after = _snapshot(location)
    changed = {k: v for k, v in after.items() if before[k] != v}
    if changed:
        audit_log(actor=user, action="location_updated", obj=location,
                  before={k: before[k] for k in changed}, after=changed)
    return location
