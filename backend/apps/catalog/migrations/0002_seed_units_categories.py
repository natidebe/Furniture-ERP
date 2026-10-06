from django.db import migrations

UNITS = [("Pieces", "pcs"), ("Set", "set")]
CATEGORIES = [
    "Office chairs",
    "Visitor chairs",
    "Executive chairs",
    "Desks",
    "Tables",
    "Shelves",
    "Cabinets",
    "Other office furniture",
]


def seed(apps, schema_editor):
    Unit = apps.get_model("catalog", "Unit")
    Category = apps.get_model("catalog", "Category")
    for name, symbol in UNITS:
        Unit.objects.get_or_create(symbol=symbol, defaults={"name": name})
    for name in CATEGORIES:
        Category.objects.get_or_create(name=name)


def unseed(apps, schema_editor):
    apps.get_model("catalog", "Category").objects.filter(name__in=CATEGORIES).delete()
    apps.get_model("catalog", "Unit").objects.filter(
        symbol__in=[symbol for _, symbol in UNITS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
