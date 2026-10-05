from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Role, User


@receiver(post_save, sender=User)
def sync_role_group(sender, instance, **kwargs):
    """Keep the user in exactly one role group, matching User.role."""
    if kwargs.get("raw"):
        return
    role_groups = Group.objects.filter(name__in=Role.values)
    current = set(instance.groups.filter(pk__in=role_groups).values_list("name", flat=True))
    if current == {instance.role}:
        return
    instance.groups.remove(*role_groups)
    group, _ = Group.objects.get_or_create(name=instance.role)
    instance.groups.add(group)
