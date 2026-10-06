# Furniture ERP — Backend Build Guide by Phase

**Stack:** Python 3.12 · Django 5.x · Django REST Framework · PostgreSQL 16 · Celery + Redis · aiogram 3
**Timeline:** 12 weeks, 5 phases. Each phase ends with a **gate** the client signs off before the next starts.
**Last updated:** 5 Oct 2026
**Layout:** the code lives in `backend/`, and `FOLDER_STRUCTURE.md` shows where every file goes.

How to use this file:

- Work through the phases in order. Each task is a checkbox, so you can tick tasks off in GitHub or your editor.
- Each phase lists **files to create**, **models**, **services**, **endpoints**, **tests** and a **definition of done**.
- Code snippets are the reference shape. Adjust names, but keep the rules: stock and money are ledgers, every change goes through a service, and corrections are reversals.
- The client's requirements are in `userequirements.md`. The decisions below settle where that text conflicts with itself or was open to more than one reading. Don't change them without the client.

## Requirements decisions

| # | Decision | Source in `userequirements.md` |
| --- | --- | --- |
| D1 | **No cost price, purchase price or profit anywhere.** The 5:43 PM message ("Do Not Record Product Cost") overrides the earlier "Cost price (admin/accountant only)". | "Payment and Pricing Requirements" |
| D2 | **A sale and a payment are separate records.** A payment can cover part of an order, specific lines, or a customer's balance. | "Payment Must Be Recorded Separately" |
| D3 | **Every payment names its account kind: Organization or Personal.** Official-receipt sales are paid only into Organization accounts, with a receipt number. Personal payments never carry a receipt number. One no-receipt order can mix both kinds (the 100,000 ETB example). | "Payment Types" A/B, "Payment Account", "Partial Payment" |
| D4 | **One tracking number per transaction.** The sales order number (`SO-…`) is the master reference. Every delivery note, stock request, release, transfer, movement and payment tied to the order stores and shows it, and search finds the whole transaction from any of those numbers. | "Delivery Paper System", "Complete Transaction History" |
| D5 | **Admins set permissions per user.** Roles give defaults; the admin adds or removes individual permissions. Accountants correct payments by default, but void or correct sales and stock only when an admin grants `correct_transactions`. | Admin "Set user permissions"; Accountant "Correct transactions when authorized" |
| D6 | **Corrections never edit or delete.** A wrong confirmed sale is voided (stock and balance reversed) and re-issued with a link to the original. A wrong payment is reversed and re-recorded with a link. Each step is in the history. | "Complete Transaction History", "Important Permission" |
| D7 | **Company total stock includes goods in transit**, shown as its own column, so transfers never make stock disappear from the total. | "Stock Management" |
| D8 | **No company delivery.** Goods leave either to a branch (transfer) or to the customer at pickup. | "Out-of-City Orders" |
| D9 | **Salespeople see only their own sales and orders.** | Salesperson "View their own sales" |
| D10 | **New sales and payments are entered on a web page**; the bot does notifications, stock requests and releases, search and quick views. The web frontend is built later, outside this plan (Q17). | Q17 answer |
| D11 | **Resellers pay a wholesale price.** Each product has a selling price and an optional wholesale price (not above the selling price). A sale to a `reseller` customer uses the wholesale price; when a product has none, the selling price. Walk-in and out-of-city customers pay the selling price. | Owner, 6 Oct 2026 (Q15) |
| D12 | **Every staff member sees Personal-account payments.** `view_personal_payments` is a default for every role; the admin can still remove it from one user. | Owner, 6 Oct 2026 (Q9) |
| D13 | **The owner sets the salesperson discount limit in the system's Settings**, later. Until set it is 0%: every discount needs `approve_discounts`. | Owner, 6 Oct 2026 (Q6) |
| D14 | **One receipt number per Organization payment**; official-receipt sales take only Organization payments (D3 confirmed). A payment with no order stays the customer's advance until the accountant allocates it. Payment accounts and credit limits are entered by the admin in the system once it is live. | Owner, 6 Oct 2026 (Q8, Q11, Q14, Q20) |

**Scope notes**
- **Web frontend (Q17, decided 5 Oct 2026):** new sales and payments are entered on a **web page**, not in the bot. The web frontend is a separate piece of work, built later on top of this API; it is not in the 12-week backend timeline. Until it exists, staff use the API (Swagger) or the Django admin for testing only. The bot covers notifications, stock requests and releases, search and quick views.
- **Cost price:** if the client later wants cost or profit, it is a scope change (D1).

---

## Table of contents

0. [Requirements decisions](#requirements-decisions)
1. [Phase 1 — Foundation (Weeks 1–2)](#phase-1--foundation-weeks-12)
2. [Phase 2 — Inventory & Stock Requests (Weeks 3–5)](#phase-2--inventory--stock-requests-weeks-35)
3. [Phase 3 — Sales, Payments & Credit (Weeks 6–8)](#phase-3--sales-payments--credit-weeks-68)
4. [Phase 4 — Telegram Bot & Reports (Weeks 9–10)](#phase-4--telegram-bot--reports-weeks-910)
5. [Phase 5 — Pilot & Go-Live (Weeks 11–12)](#phase-5--pilot--go-live-weeks-1112)
6. [Appendix A — Conventions](#appendix-a--conventions)
7. [Appendix B — Environment variables](#appendix-b--environment-variables)

---

## Phase 1 — Foundation (Weeks 1–2)

**Goal:** a running project with users, roles, locations, products (no cost price), audit log and document numbering, deployed to staging.

**Gate:** the client answers the open questions (bottom of this phase) and the data model is frozen.

### 1.1 Project setup

- [x] Repo `natidebe/Furniture-ERP` on GitHub: `Back-End` is the working branch for the backend, `main` is production.
- [x] Skeleton created in `backend/`: the full layout from `FOLDER_STRUCTURE.md` (all 12 apps, with placeholder files for later phases) plus the config, Docker, CI and requirements files below. CI lives at the repo root in `.github/workflows/ci.yml` and runs inside `backend/`. Top level:

```
backend/
  config/
    settings/
      base.py
      dev.py
      prod.py
    urls.py
    celery.py
    wsgi.py
    asgi.py
  apps/                   # core, accounts, locations, catalog, audit are built in Phase 1
  bot/                    # placeholders until Phase 4
  tests/
  requirements/
    base.txt
    dev.txt
  conftest.py
  docker-compose.yml
  Dockerfile
  .env.example
  pytest.ini
  ruff.toml
  mypy.ini
  manage.py
```

- [x] `requirements/base.txt`:

```
Django>=5.1,<5.2
djangorestframework>=3.15
djangorestframework-simplejwt>=5.3
drf-spectacular>=0.27
django-filter>=24.2
django-cors-headers>=4.4
django-simple-history>=3.7
django-axes>=6.5
psycopg[binary]>=3.2
dj-database-url>=2.2
celery>=5.4
redis>=5.0
openpyxl>=3.1
weasyprint>=62
python-decouple>=3.8
gunicorn>=22
sentry-sdk>=2.10
```

- [x] `requirements/dev.txt`: `-r base.txt`, `pytest`, `pytest-django`, `pytest-cov`, `factory-boy`, `ruff`, `mypy`, `django-stubs`, `coverage`.
- [x] `docker-compose.yml` with services: `db` (postgres:16), `redis`, `api`, `worker`, `beat`. The `bot` service is added in Phase 4. Beat uses Celery's built-in scheduler, with the schedule defined in `config/celery.py`.
- [x] `Dockerfile` installs the Pango/HarfBuzz system libraries WeasyPrint needs (used for delivery note PDFs in Phase 3).
- [x] Split settings: `base.py` (shared), `dev.py` (DEBUG, local DB), `prod.py` (security headers, Sentry, HTTPS).
- [x] Settings essentials:
  - `DATABASES` from `DATABASE_URL` via `dj-database-url`
  - `TIME_ZONE = "Africa/Addis_Ababa"`, `USE_TZ = True`
  - `AUTH_USER_MODEL = "accounts.User"`
  - DRF defaults: JWT auth, `IsAuthenticated`, `PageNumberPagination` (page size 25), `DjangoFilterBackend`, `SearchFilter`, `OrderingFilter`
  - `SPECTACULAR_SETTINGS` with title "Furniture ERP API"
- [ ] CI with GitHub Actions (`.github/workflows/ci.yml`): ruff → `makemigrations --check` → pytest with a Postgres service → build the Docker image.
- [x] Health endpoint `GET /health/` (`apps/core/views.py`) returning `{"status": "ok"}` after checking the DB connection, or 503 if the DB is down.

### 1.2 `core` app — shared base pieces

- [x] `apps/core/models.py`:

```python
from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        abstract = True


class ActiveModel(TimeStampedModel):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class DocumentSequence(models.Model):
    prefix = models.CharField(max_length=10)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("prefix", "year")
```

- [x] `apps/core/numbering.py` — gapless document numbers:

```python
from django.db import transaction
from django.utils import timezone

from .models import DocumentSequence


def next_number(prefix: str) -> str:
    """Return e.g. 'SO-2026-00125'. Must be called inside transaction.atomic()."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("next_number() must be called inside transaction.atomic()")
    year = timezone.localdate().year
    # Insert-if-missing first, so two callers starting a new year don't race on create.
    DocumentSequence.objects.bulk_create(
        [DocumentSequence(prefix=prefix, year=year)], ignore_conflicts=True
    )
    seq = DocumentSequence.objects.select_for_update().get(prefix=prefix, year=year)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"{prefix}-{year}-{seq.last_number:05d}"
```

- [x] `apps/core/exceptions.py` — `BusinessRuleError(code, message)`, mapped to HTTP 400 with `{"code": ..., "detail": ...}` by a custom DRF exception handler.
- [x] Prefixes used across the project: `SO` (sales order), `DN` (delivery note), `SR` (stock request), `SRL` (stock release), `TR` (transfer), `GR` (goods receipt), `ADJ` (adjustment), `PAY` (payment), `MV` (movement).

### 1.3 `accounts` app — users and roles

- [x] `User(AbstractUser)` fields: `full_name`, `phone`, `role` (choices: `salesperson`, `storekeeper`, `accountant`, `admin`), `home_location` (FK → Location, nullable), `telegram_id` (BigInteger, unique, nullable), `allowed_payment_accounts` (M2M → PaymentAccount, added in Phase 3).
- [x] `User.home_location` → `Location` and `Location.created_by` → `User` point at each other. Generate the `accounts` and `locations` migrations in one `makemigrations` run so Django can split the cycle.
- [x] Data migration that creates Django Groups for the four roles. A `post_save` signal keeps the group in sync with `role`.
- [x] `apps/accounts/permissions.py`:

```python
from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role in self.allowed_roles)


def role_permission(*roles):
    return type("RolePermission", (HasRole,), {"allowed_roles": roles})


IsAdmin = role_permission("admin")
IsAccountantOrAdmin = role_permission("accountant", "admin")
IsSalesStaff = role_permission("salesperson", "accountant", "admin")
IsStorekeeper = role_permission("storekeeper", "admin")
```

- [x] **Per-user permissions (D5).** `ERPPermission` choices on the User model, stored as normal Django user permissions (`accounts.<codename>`). The admin role always has all of them. `erp_permission(ERPPermission.X)` gives the DRF permission class, and `user.has_erp_permission(...)` is the check for services. Later phases check these permissions, not role names, for:

| Permission | Guards | Default roles |
| --- | --- | --- |
| `view_personal_payments` | Personal-account amounts, lists and report totals | every role (D12) |
| `verify_payments` | verify / reject a payment | accountant, admin |
| `correct_payments` | reverse a payment and re-record it | accountant, admin |
| `correct_transactions` | void / correct a sale; reverse a stock movement | admin (grant per accountant) |
| `approve_adjustments` | approve / reject stock adjustments | accountant, admin |
| `approve_credit` | confirm a sale beyond the customer's credit rules | accountant, admin |
| `approve_discounts` | discounts above the owner's limit in Settings (D13) | accountant, admin |
| `export_reports` | Excel exports | accountant, admin |

  - Defaults are applied when a user is created and reset when their role changes. After that, the admin sets the exact list per user. Every change is audited.
  - Roles still decide *which screens and records* a user reaches (for example, a storekeeper only releases from their own warehouse). Permissions decide the sensitive *actions*.

- [x] `TelegramLinkToken` model: `user`, `token` (8 characters, unique), `expires_at` (now + 10 minutes), `used_at`.
- [x] django-axes configured: lock out after 5 failed logins for 30 minutes.
- [x] Endpoints:
  - `POST /api/v1/auth/token/` and `POST /api/v1/auth/refresh/` (simplejwt; access 15 min, refresh 7 days, rotation on)
  - `GET /api/v1/auth/me/` → id, name, role, home_location, effective permissions list
  - `POST /api/v1/auth/telegram/link-code/` → creates a one-time code for the current user
  - `GET/POST/PATCH /api/v1/users/` → admin only; includes `permissions` (omit to get the role's defaults)
  - `GET /api/v1/permissions/` → the grantable permissions with their labels and default roles

### 1.4 `locations` app

- [x] `Location(ActiveModel)`: `code` (unique: `PIA`, `DEN`, `PAW`, `PIA-UG`), `name`, `type` (`shop` / `warehouse` / `sub_store`), `parent` (FK self, nullable), `can_sell` (bool), `can_release` (bool).
- [x] Data migration that seeds:

| code | name | type | parent | can_sell | can_release |
| --- | --- | --- | --- | --- | --- |
| PIA | Piassa Branch | shop | — | yes | no |
| PIA-UG | Piassa Underground Store | sub_store | PIA | yes | no |
| DEN | Denbel Branch | shop | — | yes | no |
| PAW | Pawlos Warehouse | warehouse | — | yes (pickup) | yes |

- [x] Endpoint `GET/POST/PATCH /api/v1/locations/` → read for all, write for admin only.

### 1.5 `catalog` app — products (no cost price)

- [x] `Category(ActiveModel)`: `name`, `parent` (FK self, nullable).
- [x] `Unit(models.Model)`: `name`, `symbol` (seed: pcs, set).
- [x] `Product(ActiveModel)`: `code` (unique, upper-cased on save, e.g. `VC-001`), `name`, `category` FK, `unit` FK, `selling_price` (Decimal 14,2), `wholesale_price` (Decimal 14,2, optional, > 0 and ≤ selling price — D11), `min_stock` (int, default 0), `description` (optional).
- [x] Both prices change only through `change_price(..., price_type="selling"|"wholesale")`; `PriceHistory.price_type` records which. `catalog.selectors.price_for(product, customer)` gives the price a sale uses. `import_products` and its template have an optional **Wholesale price** column.
  - **Do not add** cost, purchase price or profit fields (D1 — the client's 5:43 PM message).
  - `min_stock` is set by the admin and drives the low-stock alert (4.4).
- [x] `PriceHistory`: `product`, `old_price`, `new_price`, `changed_by`, `changed_at`, `reason`.
- [x] Service `apps/catalog/services.py`:

```python
@transaction.atomic
def change_price(*, product: Product, new_price: Decimal, user, reason: str = "") -> Product:
    if new_price <= 0:
        raise BusinessRuleError("invalid_price", "Price must be greater than zero.")
    old = product.selling_price
    product.selling_price = new_price
    product.save(update_fields=["selling_price", "updated_at"])
    PriceHistory.objects.create(product=product, old_price=old, new_price=new_price,
                                changed_by=user, reason=reason)
    audit_log(actor=user, action="price_change", obj=product,
              before={"price": str(old)}, after={"price": str(new_price)}, reason=reason)
    return product
```

- [x] Seed categories: Office chairs, Visitor chairs, Executive chairs, Desks, Tables, Shelves, Cabinets, Other office furniture.
- [x] Endpoints:
  - `GET /api/v1/products/?search=&category=&is_active=` → search over code and name
  - `POST /api/v1/products/`, `PATCH /api/v1/products/{id}/` → admin only; `selling_price` is read-only here
  - `POST /api/v1/products/{id}/change-price/` → admin only
  - `GET /api/v1/categories/`, `GET /api/v1/units/`
- [x] Management command `import_products <file.xlsx>` to load the client's current product list (code, name, category, unit, price).

### 1.6 `audit` app

- [x] `AuditLog`: `actor` FK, `action` (string), `model` (string), `object_id` (string), `before` (JSON), `after` (JSON), `reason`, `source` (`web` / `bot` / `system`), `ip`, `at` (auto, indexed).
- [x] Helper `apps/audit/services.py::audit_log(actor, action, obj, before=None, after=None, reason="", source="web")`.
- [x] Middleware `apps/audit/middleware.py` that stores the request IP and source (`X-Client: bot` header → `bot`) in a context variable for `audit_log` to read.
- [x] Register `simple_history` on Product, Location and User for field-level history.
- [ ] Register it on Customer (Phase 2.1) and PaymentAccount (Phase 3.3) when those models are created.
- [x] Endpoint `GET /api/v1/audit/?model=&object_id=&actor=&from=&to=` → accountant (read) and admin.
- [x] The AuditLog admin is read-only: no add, change or delete.

### 1.7 Phase 1 tests

- [x] `next_number` returns sequential numbers and resets each year.
- [x] `next_number` from 10 parallel threads gives 10 unique numbers (passes on Postgres in Docker).
- [x] Product code is unique and stored upper-case.
- [x] `change_price` writes PriceHistory and AuditLog.
- [x] A salesperson gets 403 on product create, change-price and users.
- [x] Login lockout after 5 bad passwords.
- [x] New users get their role's default permissions; a role change resets them; the admin can grant and remove single permissions, and each change is audited.
- [x] An accountant can correct payments by default but not sales or stock (`correct_transactions`) until granted; a deactivated user has no permissions.

### 1.8 Definition of done

- [x] `docker compose up` runs the API; `/health/` returns ok.
- [x] `/api/schema/swagger-ui/` shows all Phase 1 endpoints.
- [ ] CI is green; staging is deployed with seed data and four test users (one per role). `manage.py seed_demo` loads the users and sample data (DEBUG only).
- [ ] The client's product list is imported into staging.

### 1.9 Open questions to settle before the gate

- [ ] **Q1.** How does imported stock arrive — always into Pawlos? Who records it?
- [ ] **Q2.** Opening balances: full stock count per location? Outstanding customer balances today?
- [ ] **Q3.** Does Denbel request from Pawlos the same way? Piassa ↔ Denbel transfers?
- [ ] **Q4.** Is the Piassa underground store tracked separately from Piassa?
- [ ] **Q5.** Do out-of-city and reseller customers collect goods at Pawlos directly?
- [x] **Q6.** Can salespeople give discounts, and up to what limit? **Answer: the owner sets the limit in Settings later (D13).**
- [ ] **Q7.** How are returns and damaged goods handled today?
- [x] **Q8.** Which payment accounts exist, and which are Organization vs Personal? **Answer: the admin enters them in the system's settings once it is live (D14).**
- [x] **Q9.** Who may see Personal-account totals and reports? **Answer: every staff member (D12).**
- [ ] **Q10.** VAT or price-with-tax fields needed on official-receipt delivery notes?
- [x] **Q11.** Credit limits per customer, and who approves exceeding them? **Answer: as planned — a salesperson cannot go beyond a customer's credit rules; the accountant or admin (`approve_credit`) can. Limits are entered per customer in the system (D14).**
- [ ] **Q12.** Ethiopian calendar and Amharic needed — on screens, documents, or both?
- [ ] **Q13.** Should a printed delivery note still go to the customer, and in what layout?
- [x] **Q14.** Can an **official-receipt** order also receive Personal-account payments? Is the receipt issued once per sale or once per payment? **Answer: no Personal payments on official-receipt sales; one receipt per payment (D3, D14).**
- [x] **Q15.** Do resellers pay the same selling price as walk-in customers, or is there a wholesale price? **Answer: resellers get a wholesale price (D11).**
- [ ] **Q16.** Does a stock request need someone's approval before the Pawlos storekeeper may release it ("approved/requested transaction"), or is a salesperson's request enough?
- [x] **Q17.** Must all daily work be done in Telegram, including new sales and payments? **Answer: no. Sales and payments are entered on a web page, built later (D10).**
- [ ] **Q18.** Low-stock alert: is `min_stock` for the company total or per location? Should the stock report show the Piassa underground store as its own column?
- [ ] **Q19.** Transaction number format: the client's example uses `PS-2026-00125`. What does `PS` mean, and should sales use it instead of `SO`?
- [x] **Q20.** How should a customer payment with no order chosen be applied? **Answer: kept as the customer's advance until the accountant decides (D14).**

---

## Phase 2 — Inventory & Stock Requests (Weeks 3–5)

**Goal:** every stock change is a recorded movement; balances per location are always correct; the Pawlos storekeeper can only release against a valid request.

**Gate:** stock balances match the sum of movements, and no release is possible without a request.

### 2.1 `inventory` app — models

- [x] First create the `Customer` model (fields in 3.1) and the "Walk-in Customer" data migration in the `customers` app. Stock movements and stock requests reference customers, so the model must exist now. Register `simple_history` on it. Customer endpoints and selectors stay in Phase 3.
- [x] `StockMovement` — **immutable**, never updated or deleted:

```python
class MovementType(models.TextChoices):
    RECEIPT = "receipt"            # import arrives (outside → Pawlos)
    TRANSFER_OUT = "transfer_out"  # location → in transit
    TRANSFER_IN = "transfer_in"    # in transit → location
    SALE = "sale"                  # location → customer
    RETURN = "return"              # customer → location
    ADJUSTMENT = "adjustment"      # count / damage / loss
    REVERSAL = "reversal"          # cancels an earlier movement


class StockMovement(models.Model):
    number = models.CharField(max_length=20, unique=True)
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    qty = models.PositiveIntegerField()
    from_location = models.ForeignKey("locations.Location", null=True, blank=True,
                                      on_delete=models.PROTECT, related_name="+")
    to_location = models.ForeignKey("locations.Location", null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    type = models.CharField(max_length=20, choices=MovementType.choices)
    reference_type = models.CharField(max_length=30)   # "sales_order", "stock_release", ...
    reference_id = models.CharField(max_length=40)
    # D4: the master transaction number (the sales order's SO-…), or the SR-… number for a
    # branch restock with no order. Indexed so one search finds every movement of a transaction.
    transaction_number = models.CharField(max_length=20, blank=True, db_index=True)
    customer = models.ForeignKey("customers.Customer", null=True, blank=True,
                                 on_delete=models.PROTECT)
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    note = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    reverses = models.OneToOneField("self", null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="reversed_by")

    def save(self, *args, **kwargs):
        if self.pk:
            raise BusinessRuleError("immutable", "Stock movements cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise BusinessRuleError("immutable", "Stock movements cannot be deleted.")
```

- [x] `StockBalance`: `product`, `location`, `on_hand` (int ≥ 0), `reserved` (int ≥ 0), `updated_at`; `unique_together (product, location)`; DB `CheckConstraint`s for `on_hand >= 0`, `reserved >= 0` and `reserved <= on_hand`.
- [x] Add an **In Transit** virtual location (`code="TRANSIT"`, type `warehouse`, `can_sell=False`) by data migration, so transfers have a place to sit between out and in. Company totals always include it (D7).
- [x] `GoodsReceipt` + `GoodsReceiptLine`: `number` (GR-…), `location` (default Pawlos), `reference` (shipment / container / invoice no.), `received_at`, `note`; lines: `product`, `qty`.
- [x] `StockAdjustment`: `number` (ADJ-…), `location`, `product`, `qty_delta` (signed int), `reason` (`count` / `damage` / `loss` / `found`), `status` (`proposed` / `approved` / `rejected`), `proposed_by`, `approved_by`, `approved_at`.
- [x] `StockTransfer` + `StockTransferLine`: `number` (TR-…), `from_location`, `to_location`, `status` (`in_transit` / `received` / `cancelled`), `sent_by`, `received_by`, `received_at`, `stock_request` (FK, nullable).

### 2.2 `inventory` services — the only way stock changes

- [x] `apps/inventory/services.py`:

```python
def _lock_balance(product, location) -> StockBalance:
    bal, _ = StockBalance.objects.select_for_update().get_or_create(
        product=product, location=location, defaults={"on_hand": 0, "reserved": 0}
    )
    return bal


@transaction.atomic
def post_movement(*, product, qty, type, from_location=None, to_location=None,
                  reference_type, reference_id, person, customer=None, note="",
                  transaction_number="",
                  reverses=None, allow_reserved=False) -> StockMovement:
    if qty <= 0:
        raise BusinessRuleError("invalid_qty", "Quantity must be positive.")

    if from_location:
        src = _lock_balance(product, from_location)
        available = src.on_hand if allow_reserved else src.on_hand - src.reserved
        if qty > available:
            raise BusinessRuleError(
                "insufficient_stock",
                f"Only {available} {product.code} available at {from_location.code}.")
        src.on_hand -= qty
        if allow_reserved:
            src.reserved = max(0, src.reserved - qty)
        src.save(update_fields=["on_hand", "reserved", "updated_at"])

    if to_location:
        dst = _lock_balance(product, to_location)
        dst.on_hand += qty
        dst.save(update_fields=["on_hand", "updated_at"])

    mv = StockMovement.objects.create(
        number=next_number("MV"), product=product, qty=qty, type=type,
        from_location=from_location, to_location=to_location,
        reference_type=reference_type, reference_id=str(reference_id),
        transaction_number=transaction_number,
        person=person, customer=customer, note=note, reverses=reverses)

    transaction.on_commit(lambda: check_low_stock.delay(product.id))  # stub until Phase 4
    return mv


@transaction.atomic
def reserve(*, product, location, qty):
    bal = _lock_balance(product, location)
    if qty > bal.on_hand - bal.reserved:
        raise BusinessRuleError("insufficient_stock", "Not enough free stock to reserve.")
    bal.reserved += qty
    bal.save(update_fields=["reserved", "updated_at"])


@transaction.atomic
def unreserve(*, product, location, qty):
    bal = _lock_balance(product, location)
    bal.reserved = max(0, bal.reserved - qty)
    bal.save(update_fields=["reserved", "updated_at"])


@transaction.atomic
def reverse_movement(*, movement, person, reason) -> StockMovement:
    if hasattr(movement, "reversed_by"):
        raise BusinessRuleError("already_reversed", "Movement already reversed.")
    return post_movement(
        product=movement.product, qty=movement.qty, type=MovementType.REVERSAL,
        from_location=movement.to_location, to_location=movement.from_location,
        reference_type="reversal", reference_id=movement.number,
        person=person, note=reason, reverses=movement)
```

- [x] `apps/inventory/tasks.py::check_low_stock(product_id)`: a Celery task that does nothing for now. Phase 4.4 fills it in.
- [x] `reverse_movement` is a correction: callers must hold `correct_transactions` (D5, D6). It copies `transaction_number` from the original movement and writes an audit entry with the reason.
- [x] `receive_goods(location, reference, lines, user)` → creates a GoodsReceipt and one `receipt` movement per line (outside → Pawlos).
- [x] `propose_adjustment(...)` and `approve_adjustment(adjustment, user)`; approval posts an `adjustment` movement (negative delta = from location, positive = to location).
- [x] `send_transfer(from, to, lines, user, stock_request=None)` → `transfer_out` movements (from → TRANSIT), status `in_transit`.
- [x] `receive_transfer(transfer, user, received_lines)` → `transfer_in` movements (TRANSIT → to), status `received`. A short receipt raises a discrepancy note for the accountant.
- [x] Management command `rebuild_stock_balances [--check]`: recomputes balances from movements; `--check` only reports mismatches. Scheduled nightly in Phase 4.

### 2.3 `requests` app — Pawlos stock requests

- [x] Models:
  - `StockRequest`: `number` (SR-…), `requesting_location`, `source_location` (default Pawlos), `order` (FK → SalesOrder, nullable; the field is added by a Phase 3 migration once SalesOrder exists), `transaction_number` (the order's SO-… number, or the request's own SR-… number when there is no order — D4), `customer` (nullable), `salesperson`, `status`, `notes`, `acknowledged_by`, `acknowledged_at`.
  - `StockRequestLine`: `request`, `product`, `qty_requested`, `qty_released` (default 0).
  - `StockRelease`: `number` (SRL-…), `request`, `released_by`, `released_at`, `destination_type` (`branch` / `customer_pickup`), `note`.
  - `StockReleaseLine`: `release`, `product`, `qty`.
- [x] Status machine (enforced in services, never set directly by the API):

```
pending ──acknowledge──▶ acknowledged ──release(partial)──▶ partially_released
   │                         │                                  │
   │                         └──release(all)──▶ released ◀──────┘
   ├──reject──▶ rejected                            │
   └──cancel──▶ cancelled                          close──▶ closed
```

- [x] Services `apps/requests/services.py`:
  - `create_stock_request(requesting_location, lines, salesperson, order=None, customer=None, notes="")`
    - reserves each line at the source location (`reserve`)
    - writes a `stock_request.created` notification to the outbox (the outbox model arrives in Phase 4, so for now create `notify()` in `apps/notifications/services.py` as a stub that does nothing)
  - `acknowledge_request(request, storekeeper)` → only if status is `pending`
  - `release_stock(request, lines, storekeeper, destination_type, note="")`:

```python
@transaction.atomic
def release_stock(*, request, lines, storekeeper, destination_type, note=""):
    request = StockRequest.objects.select_for_update().get(pk=request.pk)

    if request.status not in ("acknowledged", "partially_released"):
        raise BusinessRuleError("invalid_state", "Request is not open for release.")
    if storekeeper.role != "admin" and storekeeper.home_location_id != request.source_location_id:
        raise BusinessRuleError("wrong_location", "You can only release from your warehouse.")

    release = StockRelease.objects.create(
        number=next_number("SRL"), request=request, released_by=storekeeper,
        destination_type=destination_type, note=note)

    for item in lines:                      # item = {"line_id": .., "qty": ..}
        line = request.lines.select_for_update().get(pk=item["line_id"])
        remaining = line.qty_requested - line.qty_released
        if not 0 < item["qty"] <= remaining:
            raise BusinessRuleError("qty_exceeds_request",
                                    f"{line.product.code}: max {remaining} can be released.")

        StockReleaseLine.objects.create(release=release, product=line.product, qty=item["qty"])

        if destination_type == "branch":
            send_transfer_line(...)        # Pawlos → TRANSIT, allow_reserved=True
        else:                              # customer picks up at Pawlos
            post_movement(product=line.product, qty=item["qty"], type="sale",
                          from_location=request.source_location, to_location=None,
                          customer=request.customer, reference_type="stock_release",
                          reference_id=release.number, person=storekeeper,
                          allow_reserved=True)

        line.qty_released += item["qty"]
        line.save(update_fields=["qty_released"])

    all_done = all(l.qty_released >= l.qty_requested for l in request.lines.all())
    request.status = "released" if all_done else "partially_released"
    request.save(update_fields=["status"])
    notify("stock_request.released", request)
    return release
```

  - Every movement and transfer that `release_stock` posts carries the request's `transaction_number`.
  - If the client answers Q16 with "requests need approval", add an `approved` state between `pending` and `acknowledged`, guarded by a new permission. The rule "no release without a request" holds either way.
  - `reject_request(request, storekeeper, reason)` → releases reservations.
  - `cancel_request(request, user, reason)` → salesperson (own, before any release) or admin; releases reservations.
- [x] **Rule enforcement:** stock never *leaves* a location without a document: a stock request release, an approved adjustment, or a manual transfer by an accountant or admin. Storekeepers can bring stock *in* (goods receipts at their own location), propose adjustments, and acknowledge, release or reject requests at their own warehouse. They cannot approve adjustments, send manual transfers, reverse movements, or **create stock requests**: the person who releases stock must never be the one who requested it.

### 2.2a Implementation notes (where the code differs from the snippets above, and why)

- **Releases use only their own reservation.** The snippet's `allow_reserved=True` treated *all* on-hand stock as available, so one release could take units reserved for another request. `post_movement(consume_reservation=True)` now requires `qty ≤ reserved` and lowers both `on_hand` and `reserved`.
- **No silent fixes.** `unreserve` and `consume_reservation` raise `reservation_mismatch` instead of `max(0, …)`, which would hide reservations drifting away from open requests.
- **Locking:** balance rows are created race-free (insert-if-missing) and locked in location-id order, so two movements can never deadlock. Joined `FOR UPDATE` queries lock only their own rows (`of=("self",)`), which Postgres requires when an optional relation is joined.
- **Low-stock queueing never breaks a sale.** The check is queued after commit, and a broker failure is only logged. Otherwise a saved movement could return an error and be posted twice on retry.
- **Reversal scope:** the API reverses only movements with no owning document (goods receipts). Request, transfer and sale movements are corrected through their document (Phase 3 `void_order` uses `reverse_movement(internal=True)`). A reversal cannot itself be reversed.
- **Adjustments:** also `opening_balance` as a reason (Phase 5 import). An accountant cannot approve an adjustment they proposed; an admin can. Approval re-checks free stock.
- **Short receipts:** units not received stay in TRANSIT, so company totals stay correct, and the transfer gets a discrepancy note. The accountant clears them with an approved adjustment at TRANSIT.
- **Requests:** a free-text `reference` holds the customer/order reference until sales orders exist. `close_request` ends a partly released request and frees what is left; cancel works only before any release. Customer pickup requires the request to name the customer. Reject, cancel and close require a reason.
- **The In Transit location** cannot be edited or deactivated through `/locations/`.
- **`rebuild_stock_balances`** checks `reserved` against open requests as well as `on_hand` against the ledger. It refuses to "fix" an impossible ledger, and audits every fix.

### 2.4 Phase 2 endpoints

| Method & path | Who | Notes |
| --- | --- | --- |
| `GET /api/v1/stock/?location=&product=&category=&low=true` | all | Balances with `available = on_hand − reserved` |
| `GET /api/v1/stock/summary/` | all | Product × location matrix: one column per location (Piassa, Underground per Q18, Denbel, Pawlos), **In transit**, and **Total** = all of them (D7) |
| `GET /api/v1/products/{id}/stock/` | all | One product across locations (used by the bot's `VC-001` lookup) |
| `GET /api/v1/stock/movements/?product=&location=&type=&transaction=&from=&to=` | storekeeper (own), accountant, admin | Movement history; `transaction` matches `transaction_number` |
| `POST /api/v1/stock/movements/{id}/reverse/` | `correct_transactions` | Body: `{"reason": "..."}`; reason required |
| `POST /api/v1/goods-receipts/` | storekeeper (Pawlos), accountant, admin | |
| `POST /api/v1/adjustments/` | storekeeper (propose), accountant, admin | |
| `POST /api/v1/adjustments/{id}/approve/` · `/reject/` | `approve_adjustments` | |
| `POST /api/v1/transfers/` | admin, accountant | Transfers not tied to a request |
| `POST /api/v1/transfers/{id}/receive/` | branch staff of destination, admin | |
| `GET /api/v1/stock-requests/` | salesperson (own branch), storekeeper (own warehouse), accountant, admin | Search by number, transaction, reference, customer, product code |
| `POST /api/v1/stock-requests/` | salesperson (own branch), admin | `requesting_location` defaults to your branch, `source_location` to Pawlos |
| `POST /api/v1/stock-requests/{id}/acknowledge/` | storekeeper, admin | |
| `POST /api/v1/stock-requests/{id}/release/` | storekeeper, admin | Body: `{"destination_type": "...", "lines": [{"line_id": 1, "qty": 5}]}` |
| `POST /api/v1/stock-requests/{id}/reject/` · `/cancel/` | storekeeper / requester, admin | Reason required |
| `POST /api/v1/stock-requests/{id}/close/` | requester, source storekeeper, admin | Ends a partly released request; frees the rest |
| `GET /api/v1/goods-receipts/` · `/adjustments/` · `/transfers/` | stock staff (own location) / all for accountant, admin | Transfers: anyone whose location is the source or destination |

### 2.5 Phase 2 tests

- [x] Selling or releasing more than available raises `insufficient_stock`; balance unchanged.
- [x] **Concurrency:** two threads release the last 5 units at once → exactly one succeeds (passes on Postgres in Docker).
- [x] Reserved stock cannot be sold by another order.
- [x] Release without a request is impossible (no endpoint; service refuses `pending`, `rejected`, `cancelled`, `released`).
- [x] Release above `qty_requested − qty_released` is refused.
- [x] Partial release → status `partially_released`; remaining reservation is correct.
- [x] Storekeeper from another location cannot release.
- [x] Transfer out + in leaves TRANSIT at zero and destination increased.
- [x] `reverse_movement` restores balances and cannot be applied twice.
- [x] Reversing a movement or approving an adjustment without the permission returns 403, even for an accountant.
- [x] Stock summary: Total = sum of every location column + In transit; a sent-but-not-received transfer leaves Total unchanged.
- [x] Every movement from a request release carries the request's `transaction_number`.
- [x] **Property test:** after a random sequence of 200 operations, every `StockBalance.on_hand` equals the sum of its movements (`rebuild_stock_balances --check` reports zero mismatches).
- [x] StockMovement `save()` on an existing row and `delete()` both raise.

### 2.6 Definition of done

- [ ] Goods receipt, transfer, adjustment and request → release all work on staging through Swagger.
- [x] The stock summary endpoint returns the Piassa / (Underground) / Denbel / Pawlos / In transit / Total matrix.
- [ ] `rebuild_stock_balances --check` reports no mismatch on staging.
- [ ] Client demo: storekeeper releases a partial request; the client signs the gate.

---

## Phase 3 — Sales, Payments & Credit (Weeks 6–8)

**Goal:** sales orders with delivery notes; payments recorded separately to Organization or Personal accounts; partial and per-item payments; a customer credit ledger.

**Gate:** the client's 100,000 ETB partial-payment example passes end to end.

### 3.1 `customers` app

- [ ] The model and walk-in migration were created in Phase 2.1. Here, add the selectors and endpoints.
- [ ] `Customer(ActiveModel)`: `name`, `phone` (indexed), `shop_name`, `city`, `type` (`walk_in` / `reseller` / `out_of_city`), `credit_allowed` (bool, default False), `credit_limit` (Decimal, nullable = no limit), `notes`.
- [ ] Data migration (Phase 2.1): one shared customer "Walk-in Customer" (`type=walk_in`) for anonymous cash sales.
- [ ] Phone uniqueness: warn on duplicates (soft), do not block — resellers may share a number.
- [ ] Selectors `apps/customers/selectors.py`:
  - `customer_balance(customer)` → `{"total_purchases", "total_paid", "outstanding", "advance"}`
  - `customer_statement(customer, date_from, date_to)` → chronological rows (order = debit, payment = credit) with a running balance
- [ ] Endpoints: `GET/POST/PATCH /api/v1/customers/?search=&type=&city=` (search over name, phone, shop name), `GET /customers/{id}/balance/`, `GET /customers/{id}/statement/`. Salespeople can create customers. Only users with `approve_credit` can change `credit_allowed` and `credit_limit`; the serializer makes those fields read-only for everyone else.
- [ ] The statement shows every payment with its date and account kind (Organization / Personal), as the client's "ABC Furniture" example asks. Personal amounts follow the `view_personal_payments` rule in 3.3.

### 3.2 `sales` app — orders and delivery notes

- [ ] `SalesOrder(TimeStampedModel)`:
  - `number` (SO-…): **the master transaction number (D4)**. It is printed on the delivery note and stored as `transaction_number` on every related request, release, transfer and movement.
  - `customer`, `branch` (Location), `salesperson`, `channel` (`walk_in` / `phone`)
  - `fulfillment_status`: `draft` → `pending` → `confirmed` → `prepared` → `released` → `completed`, or `cancelled` (before any release) or `voided` (a correction after release, D6). Phone orders follow the client's Pending → Confirmed → Prepared → Released.
  - `payment_status`: `unpaid` / `partial` / `paid` (computed and cached by the payment service)
  - `receipt_type`: `official` / `none`. This is the "payment type" the salesperson picks at the sale (official receipt vs without receipt). "Credit" is whatever stays unpaid after confirmation.
  - `total_amount` (Decimal, computed from lines on save), `notes`, `confirmed_at`, `cancelled_reason`
  - `replaces` (FK self, nullable): the voided order this one corrects; `voided_by`, `voided_at`, `void_reason`
- [ ] `SalesOrderLine`: `order`, `product`, `qty`, `unit_price` (snapshot copied from product at creation), `discount` (Decimal, default 0), `line_total` (= qty × unit_price − discount), `source_location`, `qty_released` (default 0).
- [ ] `DeliveryNote`: `number` (DN-…), `order`, `location`, `issued_by`, `issued_at`; `DeliveryNoteLine`: `product`, `qty`.
- [ ] Services `apps/sales/services.py`:
  - `create_order(customer, branch, lines, salesperson, channel, receipt_type, notes, payment=None, replaces=None)` → status `draft` (walk-in) or `pending` (phone). Unit prices always come from the product via `price_for(product, customer)` — the wholesale price for resellers (D11) — never from the request body. An optional `payment` (same fields as `record_payment`) is recorded in the same transaction, so a walk-in sale with immediate payment is one step.
  - `update_draft_order(order, lines, user)` → only while `draft` / `pending`.
  - `confirm_order(order, user)`:
    1. For each line where `source_location` is the branch: post a `sale` movement (branch → customer) and add it to a new DeliveryNote.
    2. For lines sourced from Pawlos: `create_stock_request(...)` linked to the order.
    3. Credit check: if the order will have an unpaid balance and `credit_allowed` is false, or the new outstanding exceeds `credit_limit`, raise `credit_not_allowed` unless the user has `approve_credit`.
    4. Set status `confirmed`, or `completed` if every line was released at the branch.
  - `release_from_branch(order, lines, user)` → after a transfer is received, sell the remaining lines from the branch and issue a DeliveryNote.
  - `mark_prepared(order, user)` / `mark_released(order, user)` → used for phone orders picked up at Pawlos (released automatically when the stock release has destination `customer_pickup`).
  - `cancel_order(order, user, reason)` → only before any release; cancels open stock requests and releases reservations.
  - `return_goods(order, lines, location, user, reason)` → `return` movements (customer → location) and reduces the order total through a negative adjustment line, so the customer balance updates.
  - `void_order(order, user, reason)` → **correction of a wrong released sale (D6)**; requires `correct_transactions` and a reason. In one transaction it:
    1. reverses every stock movement of the order (`reverse_movement`), and cancels open requests and reservations;
    2. deactivates the order's payment allocations, so that money becomes the customer's advance (the payments themselves stay valid);
    3. sets `voided`, which takes the order out of sales totals and the customer balance;
    4. writes an audit entry.

    The corrected sale is then created with `create_order(..., replaces=voided_order)`, and the advance is allocated to it. Both orders show the link in their history.
- [ ] Discount rule (D13): salesperson discounts above the limit require `approve_discounts`. The limit is a **system setting the owner edits** (stored in the database, audited, shown on a Settings page — `GET/PATCH /api/v1/settings/`, admin only), starting at 0%. `MAX_SALESPERSON_DISCOUNT_PCT` in the environment is only the starting value.
- [ ] Reseller prices (D11): `unit_price` is snapshotted from `price_for(product, customer)` when the line is created; changing the customer on a draft re-prices its lines. Tests: a reseller order uses wholesale prices; a walk-in order uses selling prices; a later price change does not alter the order.
- [ ] Delivery note PDF: `apps/sales/pdf.py` renders `apps/sales/templates/sales/delivery_note.html` with WeasyPrint. Layout: company header, **order (transaction) number** in large type, DN number, date, customer, table (code, product, qty, unit price, total), payment summary, three signature lines (salesperson, storekeeper, customer).

### 3.3 `payments` app

- [ ] `PaymentAccount(ActiveModel)`: `name`, `kind` (`organization` / `personal`), `method` (`bank` / `cash` / `mobile_money`), `bank_name`, `account_number`, `owner_name`. Register `simple_history` on it.
- [ ] `Payment(TimeStampedModel)`: `number` (PAY-…), `customer`, `account`, `amount`, `method`, `receipt_number` (nullable, indexed for search), `paid_at`, `recorded_by`, `status` (`unverified` / `verified` / `rejected` / `reversed`), `verified_by`, `verified_at`, `reversal_reason`, `replaces` (FK self, nullable: the reversed payment this one corrects), `note`.
- [ ] Payment account rules (D3):
  - An **official-receipt** order accepts allocations only from **Organization** payments, and those need a `receipt_number`.
  - A **Personal** payment never has a `receipt_number`.
  - A no-receipt order accepts both kinds, as in the 100,000 ETB example (confirmed by the owner, Q14).
  - Each Organization payment on an official-receipt sale carries its own receipt number (one receipt per payment, Q14).
- [ ] `PaymentAllocation`: `payment`, `order`, `order_line` (nullable), `amount`, `is_active` (False after reversal).
- [ ] Services `apps/payments/services.py`:

```python
@transaction.atomic
def record_payment(*, customer, account, amount, method, paid_at, recorded_by,
                   receipt_number=None, allocations=(), note="") -> Payment:
    if amount <= 0:
        raise BusinessRuleError("invalid_amount", "Amount must be positive.")
    if not account.is_active:
        raise BusinessRuleError("inactive_account", "This payment account is closed.")
    if (recorded_by.role == "salesperson"
            and not recorded_by.allowed_payment_accounts.filter(pk=account.pk).exists()):
        raise BusinessRuleError("account_not_allowed", "You cannot record to this account.")
    if account.kind == "personal" and receipt_number:
        raise BusinessRuleError("receipt_on_personal",
                                "Personal-account payments do not carry a receipt number.")

    total_alloc = sum(Decimal(a["amount"]) for a in allocations)
    if total_alloc > amount:
        raise BusinessRuleError("over_allocated", "Allocations exceed the payment amount.")

    payment = Payment.objects.create(
        number=next_number("PAY"), customer=customer, account=account, amount=amount,
        method=method, receipt_number=receipt_number, paid_at=paid_at,
        recorded_by=recorded_by, note=note,
        status="verified" if recorded_by.has_erp_permission("verify_payments") else "unverified")

    for a in allocations:          # {"order_id": .., "line_id": None | .., "amount": ..}
        _allocate(payment=payment, **a)

    audit_log(actor=recorded_by, action="payment_recorded", obj=payment,
              after={"amount": str(amount), "account": account.name, "kind": account.kind})
    if payment.status == "unverified":
        notify("payment.to_verify", payment)
    return payment


def _allocate(*, payment, order_id, amount, line_id=None):
    order = SalesOrder.objects.select_for_update().get(pk=order_id, customer=payment.customer)
    amount = Decimal(amount)
    if line_id:
        line = order.lines.get(pk=line_id)
        if amount > line_remaining(line):
            raise BusinessRuleError("over_line_balance",
                                    f"{line.product.code}: remaining is {line_remaining(line)}.")
    if amount > order_remaining(order):
        raise BusinessRuleError("over_order_balance", f"Order remaining is {order_remaining(order)}.")
    if order.fulfillment_status in ("draft", "cancelled", "voided"):
        raise BusinessRuleError("order_not_payable", f"{order.number} cannot take payments.")
    if order.receipt_type == "official":
        if payment.account.kind != "organization":
            raise BusinessRuleError("official_needs_organization",
                                    "Official-receipt sales are paid only into an Organization account.")
        if not payment.receipt_number:
            raise BusinessRuleError("receipt_required", "Official sales need a receipt number.")
    PaymentAllocation.objects.create(payment=payment, order=order, order_line_id=line_id,
                                     amount=amount)
    refresh_payment_status(order)
```

  - `allocate_payment(payment, allocations, user)` → allocate leftover (advance) money later.
  - `allocate_oldest_first(payment, user)` → spreads a customer-level payment over that customer's open orders, oldest first; any rest stays an advance. It never runs on its own: a payment without an order stays an advance until the accountant allocates it (Q20); this is a button the accountant may press.
  - `verify_payment(payment, user)` / `reject_payment(payment, user, reason)` → `verify_payments`; rejected payments deactivate their allocations.
  - `reverse_payment(payment, user, reason)` → `correct_payments`; status `reversed`, allocations `is_active=False`, refresh order statuses, audit log. Never delete.
  - `correct_payment(payment, user, reason, **corrected_fields)` → `correct_payments`; reverses the payment and records the corrected one with `replaces=payment` in the same transaction (D6). Use it for a wrong amount, account, date or receipt number.
- [ ] Visibility: Personal-account payments (amounts, lists, totals) are shown to users with `view_personal_payments` — every staff member by default (D12) — and always to the salesperson who recorded them. A user the admin removed it from sees the payment's existence and status, without the amount or account.
- [ ] Every payment's history shows who recorded it, the amount, the account, the date and time, and the related sale and customer, plus every verify, reject, reverse and correct step and who did it (the "Important Permission" requirement).
  - `refresh_payment_status(order)` → sets `unpaid` / `partial` / `paid` from active allocations.
- [ ] Selectors: `order_paid(order)`, `order_remaining(order)`, `line_paid(line)`, `line_remaining(line)`, `payment_unallocated(payment)`.
- [ ] Balance rules (put these in the code as docstrings):
  - Order paid = sum of active allocations (unverified included, flagged in the UI).
  - Order remaining = order total − order paid.
  - Customer outstanding = sum of confirmed (not cancelled, not voided) order totals − sum of non-reversed, non-rejected payments.
  - Unallocated payment money = customer advance.
- [ ] Data migration placeholder for payment accounts; real accounts are entered by the admin once the client lists them.

### 3.4 Search and transaction history (`reports` app)

The client asks that every transaction "remain searchable later" and that search be "very easy".

- [ ] `apps/reports/search.py::search(q, user, filters)` → grouped results, each limited to what `user` may see:
  - **products** by code or name: name, code, price, stock per location, total (the client's `VC-001` card). An exact code match comes first.
  - **customers** by name, phone or shop name, with their outstanding balance
  - **orders** by SO number; **delivery notes** by DN number; **stock requests** by SR number; **payments** by PAY number or receipt number
  - filters: `salesperson`, `from`, `to`, `branch`
- [ ] `apps/reports/history.py::transaction_history(number, user)` → takes *any* related number (SO, DN, SR, SRL, TR, MV, PAY) and resolves it to the master transaction. Returns:
  - a header: customer, products and codes, quantities, salesperson, source, destination, payment summary, status
  - a chronological event list: created, confirmed, requested, acknowledged, released, transferred, received, delivery note issued, payment recorded / verified / rejected / reversed / corrected, voided, re-issued. Each event shows who, when and the reason.

  This is the client's "Transaction #…" example.

### 3.5 Phase 3 endpoints

| Method & path | Who | Notes |
| --- | --- | --- |
| `GET/POST /api/v1/orders/` | salesperson (own orders only, D9), accountant, admin | Filters: number, status, payment_status, customer, branch, salesperson, date |
| `GET/PATCH /api/v1/orders/{id}/` | same | PATCH only while draft / pending |
| `POST /api/v1/orders/{id}/confirm/` | salesperson, accountant, admin | Beyond credit rules needs `approve_credit` |
| `POST /api/v1/orders/{id}/release-from-branch/` | salesperson (own branch), admin | |
| `POST /api/v1/orders/{id}/status/` | storekeeper (prepared), sales staff | Body: `{"status": "prepared"}` |
| `POST /api/v1/orders/{id}/cancel/` · `/return/` | owner before release / accountant, admin | |
| `POST /api/v1/orders/{id}/void/` | `correct_transactions` | Body: `{"reason": "..."}`; re-issue with `POST /orders/` and `"replaces": <id>` |
| `GET /api/v1/orders/{id}/history/` | same as order read | The transaction history (3.4) |
| `GET /api/v1/orders/{id}/payments/` | sales staff | Payment history with account kind and recorder |
| `GET /api/v1/orders/{id}/delivery-note.pdf` | sales staff, storekeeper | |
| `GET/POST /api/v1/payments/` | salesperson (own), accountant, admin | Filters: number, receipt_number, account, account_kind, status, customer, order, salesperson, branch, from, to. Personal amounts need `view_personal_payments` |
| `POST /api/v1/payments/{id}/allocate/` · `/allocate-oldest-first/` | accountant, admin | |
| `POST /api/v1/payments/{id}/verify/` · `/reject/` | `verify_payments` | |
| `POST /api/v1/payments/{id}/reverse/` · `/correct/` | `correct_payments` | Reason required |
| `GET /api/v1/search/?q=&salesperson=&branch=&from=&to=` | all staff | 3.4; results filtered by permissions |
| `GET /api/v1/transactions/{number}/` | all staff (own only for salespeople) | 3.4; any related number |
| `GET/POST/PATCH /api/v1/payment-accounts/` | read: staff; write: admin | Salespeople only see accounts they are allowed to use |

Example `POST /api/v1/payments/` body:

```json
{
  "customer_id": 42,
  "account_id": 1,
  "amount": "50000.00",
  "method": "bank",
  "receipt_number": "R-000981",
  "paid_at": "2026-10-03T10:30:00+03:00",
  "allocations": [
    {"order_id": 125, "line_id": 311, "amount": "50000.00"}
  ]
}
```

Example `GET /api/v1/orders/125/payments/` response:

```json
{
  "order": "SO-2026-00125",
  "total": "100000.00",
  "paid": "60000.00",
  "remaining": "40000.00",
  "payment_status": "partial",
  "payments": [
    {"number": "PAY-2026-00310", "date": "2026-10-03", "amount": "40000.00",
     "account": "CBE – Company", "kind": "organization", "status": "verified",
     "recorded_by": "Abebe"},
    {"number": "PAY-2026-00322", "date": "2026-10-05", "amount": "20000.00",
     "account": "Telebirr – Owner", "kind": "personal", "status": "unverified",
     "recorded_by": "Sara"}
  ]
}
```

### 3.6 Phase 3 tests

- [ ] **Client example:** order 100,000 → pay 40,000 Organization → pay 20,000 Personal → paid 60,000, remaining 40,000, status `partial`, two history rows with correct kinds.
- [ ] **Per-item payment:** order with chairs 50,000 + desks 40,000 + cabinet 20,000 → pay 50,000 to the chairs line → chairs line paid, desks and cabinet unpaid, order remaining 60,000.
- [ ] Allocation above the line or order remaining is refused.
- [ ] Over-allocating a payment is refused; leftover becomes an advance and can be allocated later.
- [ ] Salesperson cannot use an account outside `allowed_payment_accounts`.
- [ ] Official-receipt order + Organization account without a receipt number is refused.
- [ ] Official-receipt order + Personal account is refused (`official_needs_organization`).
- [ ] A Personal payment with a receipt number is refused (`receipt_on_personal`).
- [ ] A no-receipt order accepts both Organization and Personal payments (the client's example).
- [ ] `correct_payment` leaves the old payment `reversed`, creates the new one with `replaces`, and the order balance reflects only the new one.
- [ ] Verify, reject, reverse and correct without the matching permission return 403, even for an accountant whose permission was removed.
- [ ] A user without `view_personal_payments` never sees Personal amounts in payment lists, order payment history, customer statements or search.
- [ ] Reversing a payment restores the remaining balance and keeps the payment row.
- [ ] Customer `credit_allowed=False` → salesperson cannot confirm an order with a balance; accountant can.
- [ ] Credit limit exceeded → refused for salesperson.
- [ ] Unit price is taken from the product even if the request body sends another price.
- [ ] Price change after an order does not alter that order.
- [ ] Cancel after release is refused; return goods updates stock and customer balance.
- [ ] `void_order` restores stock at the original locations, removes the order from the customer balance, turns its allocations into advance, and needs `correct_transactions`. The re-issued order links to it, and the advance can be allocated to it.
- [ ] A salesperson sees only their own orders and payments.
- [ ] Search finds a transaction by product code, product name, customer name, customer phone, SO, DN, SR and PAY number, receipt number, salesperson and date.
- [ ] `transaction_history` returns the same timeline from the SO, DN, SR, MV and PAY numbers of one transaction, including voids and corrections.
- [ ] `allocate_oldest_first` pays the oldest open orders first and leaves the rest as advance.
- [ ] Customer statement running balance equals `customer_balance().outstanding`.
- [ ] Delivery note PDF renders and contains the DN number and all lines.

### 3.7 Definition of done

- [ ] Full walk-in flow on staging: create → confirm → delivery note PDF → payment.
- [ ] Full Pawlos flow: order → stock request → release → transfer received → branch release → payment.
- [ ] Phone order flow with partial payments and credit balance.
- [ ] Accountant verifies, rejects, reverses and corrects payments; audit log and transaction history show each action.
- [ ] Admin voids a wrong sale and re-issues it; stock, balance and history are correct.
- [ ] Client runs the 100,000 ETB example themselves and signs the gate.

---

## Phase 4 — Telegram Bot & Reports (Weeks 9–10)

**Goal:** the bot notifies the right people and handles quick actions; reports and Excel exports replace the accountant's spreadsheet.

**Gate:** the accountant signs off reports against the current Excel.

### 4.1 `notifications` app — outbox

- [ ] `NotificationOutbox`: `event_type`, `payload` (JSON), `target_user` (FK), `status` (`pending` / `sent` / `failed`), `attempts`, `last_error`, `created_at`, `sent_at`.
- [ ] Replace the Phase 2 `notify()` stub with a real function that writes outbox rows **inside the same transaction** as the business change, choosing recipients:

| Event | Recipients |
| --- | --- |
| `stock_request.created` | Storekeepers whose `home_location` = request source |
| `stock_request.released` / `.rejected` | The requesting salesperson |
| `transfer.sent` | Staff at the destination branch |
| `payment.to_verify` | All accountants |
| `stock.low` | Admins and the relevant storekeeper |
| `report.daily` / `.weekly` / `.monthly` | Admins (owner) |

- [ ] Celery task `send_pending_notifications` (`apps/notifications/tasks.py`) every 15 seconds: picks `pending` rows (`select_for_update(skip_locked=True)`), sends via the Telegram Bot API, marks `sent`; on error increments `attempts`, retries up to 5 times with backoff, then `failed`.
- [ ] Skip users without a linked `telegram_id` (they see items in the web app instead).

### 4.2 `bot` — aiogram 3 service

- [ ] Folder layout:

```
bot/
  __init__.py
  main.py             # webhook app (aiohttp), dispatcher setup
  config.py           # BOT_TOKEN, WEBHOOK_SECRET, API_BASE_URL, BOT_SERVICE_TOKEN
  api_client.py       # httpx client; sends X-Telegram-User and X-Client: bot headers
  keyboards.py        # role-based main menus, inline buttons
  handlers/
    __init__.py
    start.py          # /start <code> linking, main menu
    search.py         # free text → product lookup (e.g. VC-001)
    storekeeper.py    # requests list, acknowledge, release flow
    salesperson.py    # check stock, my orders, my sales, simple stock request
    accountant.py     # payments to verify, quick report
  requirements.txt    # aiogram, aiohttp, httpx, sentry-sdk (separate from the API image)
  Dockerfile
```

- [ ] The bot never touches the database. It only calls the REST API.
- [ ] Authentication: the bot calls the API with a service token plus the Telegram user ID. A DRF authentication class `BotUserAuthentication` (`apps/accounts/authentication.py`) resolves the linked user, so **every bot action runs with that user's normal permissions**.
- [ ] `/start <code>` → `POST /api/v1/auth/telegram/link/` with the code and the Telegram ID. Unknown Telegram IDs get only a "please link your account" message.
- [ ] Main menus (from `GET /auth/me/` role):
  - Salesperson: New Sale · Request Stock · Check Stock · Customers · Credit · My Orders · My Sales
    - **New Sale** and recording a payment open the web page (D10). Until the web frontend exists, the button explains that sales are entered on the web.
  - Storekeeper: Stock Requests · Pawlos Stock · Release Stock · Stock History
  - Accountant: Sales · Payments · Credit · Stock · Reports · Export Excel
  - Admin: all of the above
- [ ] Storekeeper release flow:
  1. Notification card: request number, branch, customer, salesperson, lines with quantities, buttons **[Acknowledge] [Release] [Reject]**.
  2. **Release** → for each line, the bot asks for the quantity actually released (defaults to remaining; buttons for the full amount or typing a number).
  3. Then asks the destination: **[To branch] [Customer pickup]**.
  4. Shows a summary and **[Confirm]** → calls `POST /stock-requests/{id}/release/` → replies with the release number.
- [ ] Search: any free-text message goes to `GET /search/` (3.4). A product code or name returns the card with name, code, price, stock per location (Piassa, Denbel, Pawlos, and Underground per Q18) and total. Customer, order, delivery, receipt and request numbers return their records, and a transaction number opens its history.
- [ ] Bot outgoing sender used by the Celery task lives in `apps/notifications/telegram.py` (plain HTTPS calls to the Bot API), so the API and bot share message formats in one place: `apps/notifications/templates.py`.
- [ ] Webhook secured with `secret_token`; add the `bot` service to `docker-compose.yml`.

### 4.3 `reports` app

- [ ] `apps/reports/selectors.py` — one function per report, each taking a `filters` dict (`date_from`, `date_to`, `branch`, `salesperson`, `customer`, `order`, `account_kind`, `account`, `category`):
  - `sales_report(filters, period)` → total sales, order count, paid vs credit, official vs no-receipt, by salesperson, by branch, products and quantities sold, best sellers; for yearly, a monthly breakdown.
  - `payments_report(filters, period)` → totals for Organization, Personal, Combined per day / week / month / year, plus a payment list. Filters: date, customer, salesperson, branch, order, account type (the client's list). For a payment, "salesperson" and "branch" mean the salesperson and branch of the order it is allocated to; an unallocated payment counts under the person who recorded it.
  - `credit_report(filters)` → outstanding per customer with ageing buckets (0–30, 31–60, 61–90, 90+ days) and credit collected in the period.
  - `stock_report(filters)` → product × location matrix (Piassa, Underground per Q18, Denbel, Pawlos, In transit, Total — D7) with a low-stock flag.
  - `movements_report(filters)` → every movement with reference and person.
  - `open_requests_report(filters)` and `unverified_payments_report(filters)`.
- [ ] What each scheduled report contains (from the requirements):

| Report | Contents |
| --- | --- |
| Daily | total sales, number of transactions, paid sales, credit sales, official-receipt sales, other (no-receipt) sales, by salesperson, by branch, products and quantities sold; money received by Organization / Personal |
| Weekly | total sales, paid, credit, outstanding credit (all customers), by salesperson, by branch, best-selling products, stock movements |
| Monthly | total sales, total paid, total credit, credit collected, outstanding customer balances, product quantities, by salesperson, by branch, stock movements |
| Yearly | the monthly contents for the whole year, with a month-by-month breakdown |

- [ ] Definitions to agree with the accountant and write into docstrings:
  - "Sales" = confirmed order totals by confirmation date (cancelled and voided excluded, returns subtracted).
  - "Paid sales" = allocations dated in the period; "credit" = sales − paid.
  - Week = Monday–Sunday in Africa/Addis_Ababa.
- [ ] `apps/reports/excel.py` → one workbook per report, formatted headers, ETB number format, totals row, frozen header, auto column widths.
- [ ] Endpoints: `GET /api/v1/reports/{sales|payments|credit|stock|movements|open-requests|unverified-payments}/?...` returning JSON; add `&format=xlsx` to download Excel.
- [ ] Permission: salespeople get only their own sales summary; storekeepers get Pawlos stock and movements; Personal-account figures are hidden unless the user has `view_personal_payments`; `format=xlsx` needs `export_reports`.

### 4.4 Scheduled jobs (Celery beat)

The schedule goes in `app.conf.beat_schedule` in `config/celery.py`.

| Task | Lives in | Schedule (Addis Ababa) | Action |
| --- | --- | --- | --- |
| `send_pending_notifications` | `apps/notifications/tasks.py` | every 15 s | Outbox → Telegram |
| `check_low_stock(product_id)` | `apps/inventory/tasks.py` | on each movement | If the company total on hand (all locations + in transit) is **below** `min_stock`, notify once per day per product. Per-location minimums only if Q18 asks for them |
| `daily_report` | `apps/reports/tasks.py` | 20:00 every day | Text summary to admins |
| `weekly_report` | `apps/reports/tasks.py` | Saturday 20:00 | Text summary + Excel file |
| `monthly_report` | `apps/reports/tasks.py` | 1st of month 08:00 | Text summary + Excel file |
| `yearly_report` | `apps/reports/tasks.py` | 1 January 08:00 | Text summary + Excel file with monthly breakdown |
| `nightly_stock_check` | `apps/inventory/tasks.py` | 02:00 | `rebuild_stock_balances --check`; alert admin on mismatch |
| `expire_link_tokens` | `apps/accounts/tasks.py` | hourly | Delete expired Telegram link codes |

Daily report message format:

```
📊 Daily Sales — 03/10/2026
Total sales: 245,000 ETB (18 orders)
Paid: 180,000 · Credit: 65,000
Official receipt: 150,000 · No receipt: 95,000
Received → Organization: 140,000 · Personal: 40,000

By branch: Piassa 190,000 · Denbel 55,000
By salesperson: Abebe 120,000 · Sara 85,000 · Kebede 40,000
Products sold: VC-001 ×20, OC-014 ×8, DS-003 ×4
```

Low-stock message format (the client's example):

```
⚠️ LOW STOCK
Office Chair A (OC-001)
Current stock: 7 pcs
Minimum: 10 pcs
```

### 4.5 Phase 4 tests

- [ ] Outbox row is created in the same transaction; a rolled-back release creates no notification.
- [ ] Failed Telegram send retries and ends `failed` after 5 attempts.
- [ ] Bot actions respect permissions: a salesperson's Telegram ID cannot release stock.
- [ ] Unlinked Telegram ID gets no data.
- [ ] Payment report: Organization + Personal = Combined for the same filters.
- [ ] Sales report totals equal the sum of confirmed order totals for the period.
- [ ] Credit report outstanding equals the sum of customer balances.
- [ ] Excel export opens with openpyxl and has the expected sheets and totals.
- [ ] Low-stock alert fires once per day, not on every movement; it fires at 7 < 10 and not at 10 = 10; stock in transit counts.
- [ ] Payments report filtered by order returns only that order's payments; Personal rows and totals are hidden without `view_personal_payments`.
- [ ] Excel export without `export_reports` returns 403.
- [ ] Yearly report monthly rows add up to the yearly totals.

### 4.6 Definition of done

- [ ] Storekeeper receives a request card in Telegram and releases stock entirely from the bot.
- [ ] Accountant gets payment-to-verify notifications; admin gets the daily report.
- [ ] All reports available in JSON and Excel on staging.
- [ ] Accountant compares one real week of reports against their Excel and signs the gate.

---

## Phase 5 — Pilot & Go-Live (Weeks 11–12)

**Goal:** real data loaded, staff trained, one week of parallel running with the paper pad and Excel, then production launch.

**Gate:** daily totals and stock counts match during the parallel run.

### 5.1 Data migration

- [ ] Management commands (all idempotent, with a `--dry-run` flag that prints what would change):
  - `import_products <xlsx>` (`catalog`; from Phase 1, rerun with the final list)
  - `import_opening_stock <xlsx>` (`inventory`) → columns `location_code, product_code, qty`; posts `adjustment` movements with reason `opening_balance`
  - `import_customers <xlsx>` (`customers`) → name, phone, shop, city, type, credit_allowed, credit_limit
  - `import_opening_balances <xlsx>` (`sales`) → creates one "Opening balance" order per customer for the amount owed, so the credit ledger starts correct
- [ ] Stock count day: the client counts Piassa, Underground, Denbel and Pawlos on the same day; import the count; freeze manual stock changes until go-live.
- [ ] Admin enters the real payment accounts (Organization / Personal) and sets `allowed_payment_accounts` per salesperson.

### 5.2 Production infrastructure

- [ ] VPS (2 vCPU, 4 GB RAM minimum), Docker Compose with `api`, `worker`, `beat`, `redis`, `bot`, `nginx`.
- [ ] Domain + HTTPS (Let's Encrypt via certbot or Caddy).
- [ ] PostgreSQL: Supabase paid plan (session pooler, dedicated role, no Supabase Auth/RLS) **or** Postgres in Compose with a volume.
- [ ] Backups: daily `pg_dump` at 03:00 to off-site storage; keep 30 daily + 12 monthly. Test one restore to staging before go-live.
- [ ] Sentry for API, worker and bot. Uptime monitor on `/health/`.
- [ ] Production settings checklist: `DEBUG=False`, `ALLOWED_HOSTS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS, CORS limited to the frontend domain, DRF throttling on auth and search.
- [ ] Set the Telegram webhook to the production URL with the secret token.

### 5.3 Training & rollout

- [ ] One short guide per role (1–2 pages, with screenshots): salesperson, storekeeper, accountant, admin.
- [ ] Training sessions: salespeople at Piassa and Denbel, the storekeeper at Pawlos, the accountant, the owner.
- [ ] Every user links their Telegram account during training.

### 5.4 Parallel run (one week)

- [ ] Staff use the system **and** the paper pad / Excel for every transaction.
- [ ] Each evening, check together with the accountant:
  - [ ] daily sales total: system vs pad
  - [ ] payments by account (Organization / Personal): system vs bank / Telebirr statements
  - [ ] spot-count 5 products per location: system vs physical
  - [ ] open stock requests: none stuck without reason
- [ ] Log every mismatch and its cause; fix bugs the same day.

### 5.5 Go-live

- [ ] Final stock spot-check, then switch off the paper pad.
- [ ] Two weeks of hypercare: daily check-in with the accountant, fast bug fixes.
- [ ] Hand over: admin credentials, backup and restore steps, how to add users and accounts, how to read the audit log.

### 5.6 Definition of done

- [ ] Five consecutive days with matching totals and no stock mismatches.
- [ ] Backups verified by a successful restore.
- [ ] Client signs off production launch.

---

## Appendix A — Conventions

- **Apps:** each app has `models.py`, `services.py` (writes, business rules), `selectors.py` (reads), `api/serializers.py`, `api/views.py`, `api/urls.py`, `admin.py`, `tests/`. Celery tasks go in `tasks.py` and commands in `management/commands/`. `core`, `reports` and `notifications` differ slightly; see `FOLDER_STRUCTURE.md`.
- **Tests:** per-app tests in `apps/<app>/tests/`, cross-app flows in `tests/`, shared fixtures in the root `conftest.py`, factories in `tests/factories.py`.
- **No business logic in views or serializers.** Views validate input with a serializer and call one service function.
- **Every service that writes** is wrapped in `transaction.atomic()`, locks the rows it changes with `select_for_update()`, and calls `audit_log()` for important changes.
- **Money:** `Decimal`, `max_digits=14, decimal_places=2`; never `float`. Serialize as strings.
- **Quantities:** positive integers; direction is shown by `from_location` / `to_location`, never by a negative qty.
- **Dates:** store UTC (`USE_TZ=True`); display and report in Africa/Addis_Ababa.
- **Errors:** raise `BusinessRuleError(code, message)`; the API returns `400 {"code": "...", "detail": "..."}` so the frontend and bot can show clear messages.
- **Commits:** small and per task, e.g. `inventory: add post_movement service with locking`.
- **Branches:** `feature/<phase>-<task>` → PR into `Back-End` → staging; `Back-End` → `main` on each phase gate → production.

## Appendix B — Environment variables

| Variable | Example | Used by |
| --- | --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` | api, worker, beat |
| `SECRET_KEY` | (random 50 chars) | api |
| `DATABASE_URL` | `postgres://erp:***@db:5432/erp` | api, worker, beat |
| `REDIS_URL` | `redis://redis:6379/0` | api, worker, beat |
| `ALLOWED_HOSTS` | `erp.example.com` | api |
| `CORS_ALLOWED_ORIGINS` | `https://app.example.com` | api |
| `SENTRY_DSN` | `https://...` | all |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` | bot, worker |
| `TELEGRAM_WEBHOOK_SECRET` | (random) | bot |
| `BOT_SERVICE_TOKEN` | (random) | bot, api |
| `API_BASE_URL` | `https://erp.example.com/api/v1` | bot |
| `MAX_SALESPERSON_DISCOUNT_PCT` | `0` | api (starting value only; the owner changes it in Settings — D13) |
| `BACKUP_BUCKET_URL` | `s3://erp-backups` | backup job |
