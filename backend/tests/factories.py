from decimal import Decimal

import factory

from apps.accounts.models import Role, User
from apps.catalog.models import Category, Product, Unit
from apps.locations.models import Location

DEFAULT_PASSWORD = "Str0ng-pass-123"


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"LOC{n}")
    name = factory.LazyAttribute(lambda o: f"Location {o.code}")
    type = "shop"
    can_sell = True


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    full_name = factory.Faker("name")
    role = Role.SALESPERSON
    password = factory.django.Password(DEFAULT_PASSWORD)


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ("name",)

    name = "Office chairs"


class UnitFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Unit
        django_get_or_create = ("symbol",)

    symbol = "pcs"
    name = "Pieces"


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    code = factory.Sequence(lambda n: f"VC-{n:03d}")
    name = factory.Sequence(lambda n: f"Visitor chair {n}")
    category = factory.SubFactory(CategoryFactory)
    unit = factory.SubFactory(UnitFactory)
    selling_price = Decimal("2500.00")


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "customers.Customer"

    name = factory.Sequence(lambda n: f"Customer {n}")
    shop_name = factory.Sequence(lambda n: f"Shop {n}")
    phone = factory.Sequence(lambda n: f"09{n:08d}")
    city = "Addis Ababa"
    type = "reseller"
