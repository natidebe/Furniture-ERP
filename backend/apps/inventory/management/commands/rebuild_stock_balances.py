from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.services import audit_log
from apps.catalog.models import Product
from apps.inventory.models import StockBalance
from apps.inventory.selectors import balance_mismatches
from apps.locations.models import Location


class Command(BaseCommand):
    help = (
        "Compare every StockBalance with the movement ledger (on hand) and open stock "
        "requests (reserved). --check only reports; without it, mismatches are fixed and "
        "each fix is written to the audit log."
    )

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true",
                            help="Report mismatches and exit with an error if any; change nothing.")

    def handle(self, *args, check, **options):
        with transaction.atomic():
            # Lock all balances so no movement lands between the comparison and the fix.
            list(StockBalance.objects.select_for_update().values_list("pk", flat=True))
            mismatches = balance_mismatches()
            if not mismatches:
                self.stdout.write(self.style.SUCCESS("All stock balances match the ledger."))
                return

            products = Product.objects.in_bulk({m["product_id"] for m in mismatches})
            locations = Location.objects.in_bulk({m["location_id"] for m in mismatches})
            for m in mismatches:
                self.stdout.write(
                    f"{products[m['product_id']].code} @ {locations[m['location_id']].code}: "
                    f"on hand {m['on_hand']} (ledger {m['expected_on_hand']}), "
                    f"reserved {m['reserved']} (open requests {m['expected_reserved']})")

            if check:
                raise CommandError(f"{len(mismatches)} balance(s) do not match the ledger.")

            for m in mismatches:
                if m["expected_reserved"] > m["expected_on_hand"] or m["expected_on_hand"] < 0:
                    raise CommandError(
                        f"Ledger itself is inconsistent for product {m['product_id']} at "
                        f"location {m['location_id']}; nothing was changed. Investigate.")
                bal, _ = StockBalance.objects.get_or_create(product_id=m["product_id"],
                                                            location_id=m["location_id"])
                bal.on_hand, bal.reserved = m["expected_on_hand"], m["expected_reserved"]
                bal.save(update_fields=["on_hand", "reserved", "updated_at"])
                audit_log(actor=None, action="stock_balance_rebuilt", obj=bal,
                          before={"on_hand": m["on_hand"], "reserved": m["reserved"]},
                          after={"on_hand": bal.on_hand, "reserved": bal.reserved})
            self.stdout.write(self.style.WARNING(f"Fixed {len(mismatches)} balance(s)."))
