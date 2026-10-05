from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Role, User
from .services import apply_role_defaults


@receiver(post_save, sender=User)
def sync_role_group(sender, instance, created, **kwargs):
    """Keep the user in exactly one role group, and give new users their role's permissions.

    Groups only label the role; ERP permissions are stored per user so an admin can
    adjust them one user at a time.
    """
    if kwargs.get("raw"):
        return
    if created:
        apply_role_defaults(instance)

    role_groups = Group.objects.filter(name__in=Role.values)
    current = set(instance.groups.filter(pk__in=role_groups).values_list("name", flat=True))
    if current == {instance.role}:
        return
    instance.groups.remove(*role_groups)
    group, _ = Group.objects.get_or_create(name=instance.role)
    instance.groups.add(group)
