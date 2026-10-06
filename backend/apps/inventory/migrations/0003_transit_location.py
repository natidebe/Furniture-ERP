from django.db import migrations

TRANSIT_CODE = "TRANSIT"


def create_transit(apps, schema_editor):
    Location = apps.get_model("locations", "Location")
    Location.objects.update_or_create(
        code=TRANSIT_CODE,
        defaults={"name": "In Transit", "type": "warehouse", "parent": None,
                  "can_sell": False, "can_release": False, "is_active": True},
    )


def remove_transit(apps, schema_editor):
    apps.get_model("locations", "Location").objects.filter(code=TRANSIT_CODE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_initial"),
        ("locations", "0002_seed_locations"),
    ]

    operations = [
        migrations.RunPython(create_transit, remove_transit),
    ]
