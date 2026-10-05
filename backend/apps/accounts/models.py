from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Fields (role, phone, home_location, telegram_id, ...) are added in Phase 1.3."""
