from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.services import create_user
from apps.catalog.models import Category, Product, Unit
from apps.catalog.services import create_product
from apps.inventory.models import StockMovement
from apps.inventory.services import receive_goods
from apps.locations.models import Location
from apps.requests.models import StockRequest
from apps.requests.services import create_stock_request

DEMO_PASSWORD = "Demo-pass-2026"

# username, full name, role, home location code
USERS = [
    ("admin", "Demo Admin", "admin", None),
    ("accountant", "Demo Accountant", "accountant", None),
    ("sales_pia", "Abebe (Piassa sales)", "salesperson", "PIA"),
    ("sales_den", "Sara (Denbel sales)", "salesperson", "DEN"),
    ("store_paw", "Kebede (Pawlos store)", "storekeeper", "PAW"),
]

# code, name, category, price, min stock
PRODUCTS = [
    ("VC-001", "Visitor chair, black mesh", "Visitor chairs", "2500", 10),
    ("OC-014", "Office chair, swivel", "Office chairs", "4800", 8),
    ("EC-010", "Executive chair, leather", "Executive chairs", "18500", 2),
    ("DS-003", "Manager desk 160 cm", "Desks", "32000", 2),
    ("CB-002", "Steel filing cabinet", "Cabinets", "12500", 3),
]

# product code → {location code: qty}
STOCK = {
    "VC-001": {"PAW": 100, "PIA": 10, "DEN": 5},
    "OC-014": {"PAW": 40, "PIA": 6, "DEN": 3},
    "EC-010": {"PAW": 6, "PIA": 1},
    "DS-003": {"PAW": 12, "PIA": 2, "DEN": 1},
    "CB-002": {"PAW": 2},  # below min stock on purpose
}


class Command(BaseCommand):
    help = ("Load demo users, products, stock and one open stock request for trying the "
            "system. Development only (refuses when DEBUG is off). Safe to rerun.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG on; never on production.")
        with transaction.atomic():
            users = self._users()
            self._products(users["admin"])
            self._stock(users["admin"])
            self._request(users["sales_pia"])
        self.stdout.write(self.style.SUCCESS(
            f"Demo data ready. Every demo user's password is: {DEMO_PASSWORD}"))
        for username, full_name, role, home in USERS:
            self.stdout.write(f"  {username:<11} {role:<12} {home or '-':<4} {full_name}")

    def _users(self) -> dict:
        users = {}
        for username, full_name, role, home in USERS:
            user = User.objects.filter(username=username).first()
            if user is None:
                user = create_user(
                    actor=None, password=DEMO_PASSWORD, username=username,
                    full_name=full_name, role=role, is_staff=(role == "admin"),
                    is_superuser=(role == "admin"),
                    home_location=Location.objects.get(code=home) if home else None)
            users[username] = user
        return users

    def _products(self, admin):
        unit = Unit.objects.get(symbol="pcs")
        for code, name, category, price, min_stock in PRODUCTS:
            if not Product.objects.filter(code=code).exists():
                create_product(user=admin, code=code, name=name, unit=unit,
                               category=Category.objects.get(name=category),
                               selling_price=Decimal(price), min_stock=min_stock)

    def _stock(self, admin):
        if StockMovement.objects.exists():
            self.stdout.write("Stock already has movements; not adding demo stock.")
            return
        by_location: dict[str, list] = {}
        for code, places in STOCK.items():
            product = Product.objects.get(code=code)
            for location, qty in places.items():
                by_location.setdefault(location, []).append({"product": product, "qty": qty})
        for location, lines in by_location.items():
            receive_goods(location=Location.objects.get(code=location), lines=lines,
                          user=admin, reference="Demo opening stock")

    def _request(self, sales):
        if StockRequest.objects.exists():
            return
        create_stock_request(
            requesting_location=Location.objects.get(code="PIA"),
            source_location=Location.objects.get(code="PAW"),
            lines=[{"product": Product.objects.get(code="VC-001"), "qty": 20},
                   {"product": Product.objects.get(code="DS-003"), "qty": 2}],
            salesperson=sales, reference="ABC Furniture, phone order",
            notes="Demo request: customer collects tomorrow")
