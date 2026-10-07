from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.importing import ProductImportError, import_products, write_template


class Command(BaseCommand):
    help = (
        "Import or update products from an .xlsx file with columns: code, name, category, "
        "unit, price, and optionally wholesale price, min stock and description. Idempotent: "
        "existing codes "
        "are updated and price changes go through change_price, so PriceHistory is kept. "
        "Any error aborts the whole import. Use --template to write a blank file to fill in."
    )

    def add_arguments(self, parser):
        parser.add_argument("file", nargs="?")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change without saving anything.")
        parser.add_argument("--user", help="Username recorded as the actor (default: system).")
        parser.add_argument("--template", metavar="OUT.xlsx",
                            help="Write a template spreadsheet to fill in, then exit.")

    def handle(self, *args, file, dry_run, user, template, **options):
        if template:
            write_template(template)
            self.stdout.write(self.style.SUCCESS(f"Template written to {template}"))
            return
        if not file:
            raise CommandError("Give the .xlsx file to import, or --template OUT.xlsx.")

        try:
            counts = import_products(file, user=self._get_actor(user), dry_run=dry_run)
        except ProductImportError as exc:
            raise CommandError(str(exc)) from exc

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
