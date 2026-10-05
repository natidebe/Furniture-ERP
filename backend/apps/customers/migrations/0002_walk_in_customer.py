from django.db import migrations

WALK_IN_CUSTOMER_NAME = "Walk-in Customer"


def create_walk_in(apps, schema_editor):
    Customer = apps.get_model("customers", "Customer")
    if not Customer.objects.filter(name=WALK_IN_CUSTOMER_NAME, type="walk_in").exists():
        Customer.objects.create(name=WALK_IN_CUSTOMER_NAME, type="walk_in",
                                notes="Shared customer for anonymous cash sales.")


def remove_walk_in(apps, schema_editor):
    apps.get_model("customers", "Customer").objects.filter(
        name=WALK_IN_CUSTOMER_NAME, type="walk_in").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_walk_in, remove_walk_in),
    ]
