from django.db import migrations

# code, name, type, parent code, can_sell, can_release
LOCATIONS = [
    ("PIA", "Piassa Branch", "shop", None, True, False),
    ("PIA-UG", "Piassa Underground Store", "sub_store", "PIA", True, False),
    ("DEN", "Denbel Branch", "shop", None, True, False),
    ("PAW", "Pawlos Warehouse", "warehouse", None, True, True),  # can_sell = customer pickup
]


def seed_locations(apps, schema_editor):
    Location = apps.get_model("locations", "Location")
    for code, name, type_, parent_code, can_sell, can_release in LOCATIONS:
        parent = Location.objects.get(code=parent_code) if parent_code else None
        Location.objects.update_or_create(
            code=code,
            defaults={"name": name, "type": type_, "parent": parent,
                      "can_sell": can_sell, "can_release": can_release},
        )


def remove_locations(apps, schema_editor):
    Location = apps.get_model("locations", "Location")
    codes = [row[0] for row in LOCATIONS]
    Location.objects.filter(code__in=codes, parent__isnull=False).delete()
    Location.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("locations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_locations, remove_locations),
    ]
