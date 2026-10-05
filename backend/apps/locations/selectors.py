from .models import Location


def active_locations():
    return Location.objects.filter(is_active=True)


def selling_locations():
    return active_locations().filter(can_sell=True)


def releasing_locations():
    return active_locations().filter(can_release=True)
