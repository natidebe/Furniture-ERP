from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from openpyxl import load_workbook

from apps.catalog import services
from apps.catalog.models import Category, Product, Unit

COLUMNS = ("code", "name", "category", "unit", "price")


class Command(BaseCommand):
    help = (
        "Import or update products from an .xlsx file with columns: code, name, category, "
        "unit, price. Idempotent: existing codes are updated and price changes go through "
        "change_price, so PriceHistory is kept. Any error aborts the whole import."
    )

    def add_arguments(self, parser):
        parser.add_argument("file")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change without saving anything.")
        parser.add_argument("--user", help="Username recorded as the actor (default: system).")

    def handle(self, *args, file, dry_run, user, **options):
        actor = self._get_actor(user)
        rows = list(self._read_rows(file))
        counts = {"created": 0, "updated": 0, "price_changed": 0, "unchanged": 0}
        errors = []

        with transaction.atomic():
            for line_no, row in rows:
                try:
                    result = self._import_row(row, actor)
                except (CommandError, ValueError) as exc:
                    errors.append(f"row {line_no}: {exc}")
                    continue
                for key in result:
                    counts[key] += 1

            if errors:
                transaction.set_rollback(True)
                raise CommandError("Nothing imported. Fix these rows:\n  " + "\n  ".join(errors))
            if dry_run:
                transaction.set_rollback(True)

        summary = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in counts.items())
        prefix = "Dry run — would import: " if dry_run else "Imported: "
        self.stdout.write(self.style.SUCCESS(prefix + summary))

    def _get_actor(self, username):
        if not username:
            return None
        try:
            return get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as exc:
            raise CommandError(f"User {username!r} not found.") from exc

    def _read_rows(self, path):
        try:
            sheet = load_workbook(path, read_only=True, data_only=True).active
        except FileNotFoundError as exc:
            raise CommandError(f"File not found: {path}") from exc
        rows = sheet.iter_rows(values_only=True)
        header = [str(cell or "").strip().lower() for cell in next(rows, ())]
        missing = [c for c in COLUMNS if c not in header]
        if missing:
            raise CommandError(f"Missing columns: {', '.join(missing)}")
        index = {c: header.index(c) for c in COLUMNS}
        for line_no, values in enumerate(rows, start=2):
            if not any(values):
                continue
            yield line_no, {c: values[i] for c, i in index.items()}

    def _import_row(self, row, actor) -> list[str]:
        code = str(row["code"] or "").strip().upper()
        name = str(row["name"] or "").strip()
        if not code or not name:
            raise ValueError("code and name are required")
        try:
            price = Decimal(str(row["price"])).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError) as exc:
            raise ValueError(f"invalid price {row['price']!r}") from exc
        if price <= 0:
            raise ValueError("price must be greater than zero")

        category_name = str(row["category"] or "").strip()
        if not category_name:
            raise ValueError("category is required")
        category, _ = Category.objects.get_or_create(name=category_name,
                                                     defaults={"created_by": actor})

        unit_name = str(row["unit"] or "").strip()
        unit = Unit.objects.filter(Q(symbol__iexact=unit_name) | Q(name__iexact=unit_name)).first()
        if unit is None:
            raise ValueError(f"unknown unit {unit_name!r}")

        product = Product.objects.filter(code=code).first()
        if product is None:
            services.create_product(user=actor, code=code, name=name, category=category,
                                    unit=unit, selling_price=price)
            return ["created"]

        result = []
        details = {"name": name, "category": category, "unit": unit}
        if any(getattr(product, k) != v for k, v in details.items()):
            product = services.update_product(user=actor, product=product, **details)
            result.append("updated")
        if product.selling_price != price:
            services.change_price(product=product, new_price=price, user=actor,
                                  reason="import_products")
            result.append("price_changed")
        return result or ["unchanged"]
