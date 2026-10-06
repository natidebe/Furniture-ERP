from django.db import migrations

CODENAME = "view_personal_payments"


def grant_to_all(apps, schema_editor):
    """Owner's answer to Q9: every staff member sees Personal-account payments.
    New users get it from their role defaults; this gives it to users who already exist."""
    Permission = apps.get_model("auth", "Permission")
    User = apps.get_model("accounts", "User")
    permission = Permission.objects.filter(content_type__app_label="accounts",
                                           codename=CODENAME).first()
    if permission is None:  # fresh database: permissions are created after migrate
        return
    for user in User.objects.all():
        user.user_permissions.add(permission)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_erp_permissions"),
    ]

    operations = [
        migrations.RunPython(grant_to_all, migrations.RunPython.noop),
    ]
