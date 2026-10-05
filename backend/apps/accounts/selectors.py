from .models import User


def staff_users():
    return User.objects.select_related("home_location").order_by("full_name", "username")
