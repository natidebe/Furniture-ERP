# Furniture ERP — Backend Build Guide by Phase

**Stack:** Python 3.12 · Django 5.x · Django REST Framework · PostgreSQL 16 · Celery + Redis · aiogram 3
**Timeline:** 12 weeks, 5 phases. Each phase ends with a **gate** the client signs off before the next starts.
**Last updated:** 5 Oct 2026
**Layout:** the code lives in `backend/`, and `FOLDER_STRUCTURE.md` shows where every file goes.

How to use this file:

- Work through the phases in order. Each task is a checkbox, so you can tick tasks off in GitHub or your editor.
- Each phase lists **files to create**, **models**, **services**, **endpoints**, **tests** and a **definition of done**.
- Code snippets are the reference shape. Adjust names, but keep the rules: stock and money are ledgers, every change goes through a service, and corrections are reversals.

---

## Table of contents

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

- [x] Create the repo with `main` and `develop` branches (local; push to GitHub to enable CI).
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

- [x] `TelegramLinkToken` model: `user`, `token` (8 characters, unique), `expires_at` (now + 10 minutes), `used_at`.
- [x] django-axes configured: lock out after 5 failed logins for 30 minutes.
- [x] Endpoints:
  - `POST /api/v1/auth/token/` and `POST /api/v1/auth/refresh/` (simplejwt; access 15 min, refresh 7 days, rotation on)
  - `GET /api/v1/auth/me/` → id, name, role, home_location, permissions list
  - `POST /api/v1/auth/telegram/link-code/` → creates a one-time code for the current user
  - `GET/POST/PATCH /api/v1/users/` → admin only

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
- [x] `Product(ActiveModel)`: `code` (unique, upper-cased on save, e.g. `VC-001`), `name`, `category` FK, `unit` FK, `selling_price` (Decimal 14,2), `min_stock` (int, default 0), `description` (optional).
  - **Do not add** cost, purchase price or profit fields.
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
- [x] Register `simple_history` on Product, Customer, PaymentAccount, Location and User for field-level history.
- [x] Endpoint `GET /api/v1/audit/?model=&object_id=&actor=&from=&to=` → accountant (read) and admin.
- [x] The AuditLog admin is read-only: no add, change or delete.

### 1.7 Phase 1 tests

- [x] `next_number` returns sequential numbers and resets each year.
- [ ] `next_number` from 10 parallel threads gives 10 unique numbers (Postgres test DB). Written; skipped on SQLite, so it first runs in CI.
- [x] Product code is unique and stored upper-case.
- [x] `change_price` writes PriceHistory and AuditLog.
- [x] A salesperson gets 403 on product create, change-price and users.
- [x] Login lockout after 5 bad passwords.

### 1.8 Definition of done

- [ ] `docker compose up` runs the API; `/health/` returns ok.
- [ ] `/api/schema/swagger-ui/` shows all Phase 1 endpoints.
- [ ] CI is green; staging is deployed with seed data and four test users (one per role).
- [ ] The client's product list is imported into staging.

### 1.9 Open questions to settle before the gate

- [ ] How does imported stock arrive — always into Pawlos? Who records it?
- [ ] Opening balances: full stock count per location? Outstanding customer balances today?
- [ ] Does Denbel request from Pawlos the same way? Piassa ↔ Denbel transfers?
- [ ] Is the Piassa underground store tracked separately from Piassa?
- [ ] Do out-of-city and reseller customers collect goods at Pawlos directly?
- [ ] Can salespeople give discounts, and up to what limit?
- [ ] How are returns and damaged goods handled today?
- [ ] Which payment accounts exist, and which are Organization vs Personal?
- [ ] Who may see Personal-account totals and reports?
- [ ] VAT or price-with-tax fields needed on official-receipt delivery notes?
- [ ] Credit limits per customer, and who approves exceeding them?
- [ ] Ethiopian calendar and Amharic needed — on screens, documents, or both?
- [ ] Should a printed delivery note still go to the customer, and in what layout?

---

## Phase 2 — Inventory & Stock Requests (Weeks 3–5)

**Goal:** every stock change is a recorded movement; balances per location are always correct; the Pawlos storekeeper can only release against a valid request.

**Gate:** stock balances match the sum of movements, and no release is possible without a request.

### 2.1 `inventory` app — models

- [ ] First create the `Customer` model (fields in 3.1) and the "Walk-in Customer" data migration in the `customers` app. Stock movements and stock requests reference customers, so the model must exist now. Customer endpoints and selectors stay in Phase 3.
- [ ] `StockMovement` — **immutable**, never updated or deleted:

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

- [ ] `StockBalance`: `product`, `location`, `on_hand` (int ≥ 0), `reserved` (int ≥ 0), `updated_at`; `unique_together (product, location)`; DB `CheckConstraint`s for `on_hand >= 0`, `reserved >= 0` and `reserved <= on_hand`.
- [ ] Add an **In Transit** virtual location (`code="TRANSIT"`, type `warehouse`, `can_sell=False`) by data migration, so transfers have a place to sit between out and in.
- [ ] `GoodsReceipt` + `GoodsReceiptLine`: `number` (GR-…), `location` (default Pawlos), `reference` (shipment / container / invoice no.), `received_at`, `note`; lines: `product`, `qty`.
- [ ] `StockAdjustment`: `number` (ADJ-…), `location`, `product`, `qty_delta` (signed int), `reason` (`count` / `damage` / `loss` / `found`), `status` (`proposed` / `approved` / `rejected`), `proposed_by`, `approved_by`, `approved_at`.
- [ ] `StockTransfer` + `StockTransferLine`: `number` (TR-…), `from_location`, `to_location`, `status` (`in_transit` / `received` / `cancelled`), `sent_by`, `received_by`, `received_at`, `stock_request` (FK, nullable).

### 2.2 `inventory` services — the only way stock changes

- [ ] `apps/inventory/services.py`:

```python
def _lock_balance(product, location) -> StockBalance:
    bal, _ = StockBalance.objects.select_for_update().get_or_create(
        product=product, location=location, defaults={"on_hand": 0, "reserved": 0}
    )
    return bal


@transaction.atomic
def post_movement(*, product, qty, type, from_location=None, to_location=None,
                  reference_type, reference_id, person, customer=None, note="",
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

- [ ] `apps/inventory/tasks.py::check_low_stock(product_id)`: a Celery task that does nothing for now. Phase 4.4 fills it in.
- [ ] `receive_goods(location, reference, lines, user)` → creates a GoodsReceipt and one `receipt` movement per line (outside → Pawlos).
- [ ] `propose_adjustment(...)` and `approve_adjustment(adjustment, user)`; approval posts an `adjustment` movement (negative delta = from location, positive = to location).
- [ ] `send_transfer(from, to, lines, user, stock_request=None)` → `transfer_out` movements (from → TRANSIT), status `in_transit`.
- [ ] `receive_transfer(transfer, user, received_lines)` → `transfer_in` movements (TRANSIT → to), status `received`. A short receipt raises a discrepancy note for the accountant.
- [ ] Management command `rebuild_stock_balances [--check]`: recomputes balances from movements; `--check` only reports mismatches. Scheduled nightly in Phase 4.

### 2.3 `requests` app — Pawlos stock requests

- [ ] Models:
  - `StockRequest`: `number` (SR-…), `requesting_location`, `source_location` (default Pawlos), `order` (FK → SalesOrder, nullable; the field is added by a Phase 3 migration once SalesOrder exists), `customer` (nullable), `salesperson`, `status`, `notes`, `acknowledged_by`, `acknowledged_at`.
  - `StockRequestLine`: `request`, `product`, `qty_requested`, `qty_released` (default 0).
  - `StockRelease`: `number` (SRL-…), `request`, `released_by`, `released_at`, `destination_type` (`branch` / `customer_pickup`), `note`.
  - `StockReleaseLine`: `release`, `product`, `qty`.
- [ ] Status machine (enforced in services, never set directly by the API):

```
pending ──acknowledge──▶ acknowledged ──release(partial)──▶ partially_released
   │                         │                                  │
   │                         └──release(all)──▶ released ◀──────┘
   ├──reject──▶ rejected                            │
   └──cancel──▶ cancelled                          close──▶ closed
```

- [ ] Services `apps/requests/services.py`:
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

  - `reject_request(request, storekeeper, reason)` → releases reservations.
  - `cancel_request(request, user, reason)` → salesperson (own, before any release) or admin; releases reservations.
- [ ] **Rule enforcement:** there is no endpoint that lets a storekeeper move stock without a `request_id`. Storekeepers have no access to `adjustments/approve`, `transfers` create, or `post_movement` directly.

### 2.4 Phase 2 endpoints

| Method & path | Who | Notes |
| --- | --- | --- |
| `GET /api/v1/stock/?location=&product=&category=&low=true` | all | Balances with `available = on_hand − reserved` |
| `GET /api/v1/stock/summary/` | all | Product × location matrix with total column |
| `GET /api/v1/products/{id}/stock/` | all | One product across locations (used by the bot's `VC-001` lookup) |
| `GET /api/v1/stock/movements/?product=&location=&type=&from=&to=` | storekeeper (own), accountant, admin | Movement history |
| `POST /api/v1/goods-receipts/` | storekeeper (Pawlos), accountant, admin | |
| `POST /api/v1/adjustments/` | storekeeper (propose), accountant, admin | |
| `POST /api/v1/adjustments/{id}/approve/` · `/reject/` | accountant, admin | |
| `POST /api/v1/transfers/` | admin, accountant | Transfers not tied to a request |
| `POST /api/v1/transfers/{id}/receive/` | branch staff of destination, admin | |
| `GET/POST /api/v1/stock-requests/` | salesperson (own branch), storekeeper (own warehouse), accountant (read), admin | |
| `POST /api/v1/stock-requests/{id}/acknowledge/` | storekeeper, admin | |
| `POST /api/v1/stock-requests/{id}/release/` | storekeeper, admin | Body: `{"destination_type": "...", "lines": [{"line_id": 1, "qty": 5}]}` |
| `POST /api/v1/stock-requests/{id}/reject/` · `/cancel/` | storekeeper / requester, admin | |

### 2.5 Phase 2 tests

- [ ] Selling or releasing more than available raises `insufficient_stock`; balance unchanged.
- [ ] **Concurrency:** two threads release the last 5 units at once → exactly one succeeds.
- [ ] Reserved stock cannot be sold by another order.
- [ ] Release without a request is impossible (no endpoint; service refuses `pending`, `rejected`, `cancelled`, `released`).
- [ ] Release above `qty_requested − qty_released` is refused.
- [ ] Partial release → status `partially_released`; remaining reservation is correct.
- [ ] Storekeeper from another location cannot release.
- [ ] Transfer out + in leaves TRANSIT at zero and destination increased.
- [ ] `reverse_movement` restores balances and cannot be applied twice.
- [ ] **Property test:** after a random sequence of 200 operations, every `StockBalance.on_hand` equals the sum of its movements (`rebuild_stock_balances --check` reports zero mismatches).
- [ ] StockMovement `save()` on an existing row and `delete()` both raise.

### 2.6 Definition of done

- [ ] Goods receipt, transfer, adjustment and request → release all work on staging through Swagger.
- [ ] The stock summary endpoint returns the Piassa / Underground / Denbel / Pawlos / Total matrix.
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
- [ ] Endpoints: `GET/POST/PATCH /api/v1/customers/`, `GET /customers/{id}/balance/`, `GET /customers/{id}/statement/`. Only accountant and admin can change `credit_allowed` and `credit_limit` (serializer makes them read-only for salespeople).

### 3.2 `sales` app — orders and delivery notes

- [ ] `SalesOrder(TimeStampedModel)`:
  - `number` (SO-…), `customer`, `branch` (Location), `salesperson`, `channel` (`walk_in` / `phone`)
  - `fulfillment_status`: `draft` → `pending` → `confirmed` → `prepared` → `released` → `completed`, or `cancelled`
  - `payment_status`: `unpaid` / `partial` / `paid` (computed and cached by the payment service)
  - `receipt_type`: `official` / `none`
  - `total_amount` (Decimal, computed from lines on save), `notes`, `confirmed_at`, `cancelled_reason`
- [ ] `SalesOrderLine`: `order`, `product`, `qty`, `unit_price` (snapshot copied from product at creation), `discount` (Decimal, default 0), `line_total` (= qty × unit_price − discount), `source_location`, `qty_released` (default 0).
- [ ] `DeliveryNote`: `number` (DN-…), `order`, `location`, `issued_by`, `issued_at`; `DeliveryNoteLine`: `product`, `qty`.
- [ ] Services `apps/sales/services.py`:
  - `create_order(customer, branch, lines, salesperson, channel, receipt_type, notes)` → status `draft` (walk-in) or `pending` (phone). Unit prices always come from the product, never from the request body.
  - `update_draft_order(order, lines, user)` → only while `draft` / `pending`.
  - `confirm_order(order, user)`:
    1. For each line where `source_location` is the branch: post a `sale` movement (branch → customer) and add it to a new DeliveryNote.
    2. For lines sourced from Pawlos: `create_stock_request(...)` linked to the order.
    3. Credit check: if the order will have an unpaid balance and `credit_allowed` is false, or the new outstanding exceeds `credit_limit`, raise `credit_not_allowed` unless the user is accountant or admin.
    4. Set status `confirmed`, or `completed` if every line was released at the branch.
  - `release_from_branch(order, lines, user)` → after a transfer is received, sell the remaining lines from the branch and issue a DeliveryNote.
  - `mark_prepared(order, user)` / `mark_released(order, user)` → used for phone orders picked up at Pawlos (released automatically when the stock release has destination `customer_pickup`).
  - `cancel_order(order, user, reason)` → only before any release; cancels open stock requests and releases reservations.
  - `return_goods(order, lines, location, user, reason)` → `return` movements (customer → location) and reduces the order total through a negative adjustment line, so the customer balance updates.
- [ ] Discount rule: salesperson discounts above a configurable limit (setting `MAX_SALESPERSON_DISCOUNT_PCT`, default 0 until the client answers) require accountant or admin.
- [ ] Delivery note PDF: `apps/sales/pdf.py` renders `apps/sales/templates/sales/delivery_note.html` with WeasyPrint. Layout: company header, DN number, order number, date, customer, table (code, product, qty, unit price, total), payment summary, three signature lines (salesperson, storekeeper, customer).

### 3.3 `payments` app

- [ ] `PaymentAccount(ActiveModel)`: `name`, `kind` (`organization` / `personal`), `method` (`bank` / `cash` / `mobile_money`), `bank_name`, `account_number`, `owner_name`.
- [ ] `Payment(TimeStampedModel)`: `number` (PAY-…), `customer`, `account`, `amount`, `method`, `receipt_number` (nullable), `paid_at`, `recorded_by`, `status` (`unverified` / `verified` / `rejected` / `reversed`), `verified_by`, `verified_at`, `reversal_reason`, `note`.
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

    total_alloc = sum(Decimal(a["amount"]) for a in allocations)
    if total_alloc > amount:
        raise BusinessRuleError("over_allocated", "Allocations exceed the payment amount.")

    payment = Payment.objects.create(
        number=next_number("PAY"), customer=customer, account=account, amount=amount,
        method=method, receipt_number=receipt_number, paid_at=paid_at,
        recorded_by=recorded_by, note=note,
        status="verified" if recorded_by.role in ("accountant", "admin") else "unverified")

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
    if order.receipt_type == "official" and payment.account.kind == "organization" \
            and not payment.receipt_number:
        raise BusinessRuleError("receipt_required", "Official sales need a receipt number.")
    PaymentAllocation.objects.create(payment=payment, order=order, order_line_id=line_id,
                                     amount=amount)
    refresh_payment_status(order)
```

  - `allocate_payment(payment, allocations, user)` → allocate leftover (advance) money later.
  - `verify_payment(payment, user)` / `reject_payment(payment, user, reason)` → accountant / admin; rejected payments deactivate their allocations.
  - `reverse_payment(payment, user, reason)` → status `reversed`, allocations `is_active=False`, refresh order statuses, audit log. Never delete.
  - `refresh_payment_status(order)` → sets `unpaid` / `partial` / `paid` from active allocations.
- [ ] Selectors: `order_paid(order)`, `order_remaining(order)`, `line_paid(line)`, `line_remaining(line)`, `payment_unallocated(payment)`.
- [ ] Balance rules (put these in the code as docstrings):
  - Order paid = sum of active allocations (unverified included, flagged in the UI).
  - Order remaining = order total − order paid.
  - Customer outstanding = sum of confirmed order totals − sum of non-reversed, non-rejected payments.
  - Unallocated payment money = customer advance.
- [ ] Data migration placeholder for payment accounts; real accounts are entered by the admin once the client lists them.

### 3.4 Phase 3 endpoints

| Method & path | Who | Notes |
| --- | --- | --- |
| `GET/POST /api/v1/orders/` | salesperson (own branch), accountant, admin | Filters: status, payment_status, customer, branch, salesperson, date |
| `GET/PATCH /api/v1/orders/{id}/` | same | PATCH only while draft / pending |
| `POST /api/v1/orders/{id}/confirm/` | salesperson, accountant, admin | |
| `POST /api/v1/orders/{id}/release-from-branch/` | salesperson (own branch), admin | |
| `POST /api/v1/orders/{id}/status/` | storekeeper (prepared), sales staff | Body: `{"status": "prepared"}` |
| `POST /api/v1/orders/{id}/cancel/` · `/return/` | owner before release / accountant, admin | |
| `GET /api/v1/orders/{id}/payments/` | sales staff | Payment history with account kind and recorder |
| `GET /api/v1/orders/{id}/delivery-note.pdf` | sales staff, storekeeper | |
| `GET/POST /api/v1/payments/` | salesperson (own), accountant, admin | Filters: account, account_kind, status, customer, salesperson, from, to |
| `POST /api/v1/payments/{id}/allocate/` | accountant, admin | |
| `POST /api/v1/payments/{id}/verify/` · `/reject/` · `/reverse/` | accountant, admin | |
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

### 3.5 Phase 3 tests

- [ ] **Client example:** order 100,000 → pay 40,000 Organization → pay 20,000 Personal → paid 60,000, remaining 40,000, status `partial`, two history rows with correct kinds.
- [ ] **Per-item payment:** order with chairs 50,000 + desks 40,000 + cabinet 20,000 → pay 50,000 to the chairs line → chairs line paid, desks and cabinet unpaid, order remaining 60,000.
- [ ] Allocation above the line or order remaining is refused.
- [ ] Over-allocating a payment is refused; leftover becomes an advance and can be allocated later.
- [ ] Salesperson cannot use an account outside `allowed_payment_accounts`.
- [ ] Official-receipt order + Organization account without a receipt number is refused.
- [ ] Reversing a payment restores the remaining balance and keeps the payment row.
- [ ] Customer `credit_allowed=False` → salesperson cannot confirm an order with a balance; accountant can.
- [ ] Credit limit exceeded → refused for salesperson.
- [ ] Unit price is taken from the product even if the request body sends another price.
- [ ] Price change after an order does not alter that order.
- [ ] Cancel after release is refused; return goods updates stock and customer balance.
- [ ] Customer statement running balance equals `customer_balance().outstanding`.
- [ ] Delivery note PDF renders and contains the DN number and all lines.

### 3.6 Definition of done

- [ ] Full walk-in flow on staging: create → confirm → delivery note PDF → payment.
- [ ] Full Pawlos flow: order → stock request → release → transfer received → branch release → payment.
- [ ] Phone order flow with partial payments and credit balance.
- [ ] Accountant verifies, rejects and reverses payments; audit log shows each action.
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
  - Salesperson: New Sale (deep link to web) · Request Stock · Check Stock · Customers · Credit · My Orders · My Sales
  - Storekeeper: Stock Requests · Pawlos Stock · Release Stock · Stock History
  - Accountant: Sales · Payments · Credit · Stock · Reports · Export Excel
  - Admin: all of the above
- [ ] Storekeeper release flow:
  1. Notification card: request number, branch, customer, salesperson, lines with quantities, buttons **[Acknowledge] [Release] [Reject]**.
  2. **Release** → for each line, the bot asks for the quantity actually released (defaults to remaining; buttons for the full amount or typing a number).
  3. Then asks the destination: **[To branch] [Customer pickup]**.
  4. Shows a summary and **[Confirm]** → calls `POST /stock-requests/{id}/release/` → replies with the release number.
- [ ] Product lookup: any message matching a product code or name → card with name, code, price, stock per location, total.
- [ ] Bot outgoing sender used by the Celery task lives in `apps/notifications/telegram.py` (plain HTTPS calls to the Bot API), so the API and bot share message formats in one place: `apps/notifications/templates.py`.
- [ ] Webhook secured with `secret_token`; add the `bot` service to `docker-compose.yml`.

### 4.3 `reports` app

- [ ] `apps/reports/selectors.py` — one function per report, each taking a `filters` dict (`date_from`, `date_to`, `branch`, `salesperson`, `customer`, `account_kind`, `account`, `category`):
  - `sales_report(filters, period)` → total sales, order count, paid vs credit, official vs no-receipt, by salesperson, by branch, products and quantities sold, best sellers; for yearly, a monthly breakdown.
  - `payments_report(filters, period)` → totals for Organization, Personal, Combined per day / week / month / year, plus a payment list.
  - `credit_report(filters)` → outstanding per customer with ageing buckets (0–30, 31–60, 61–90, 90+ days) and credit collected in the period.
  - `stock_report(filters)` → product × location matrix with total and low-stock flag.
  - `movements_report(filters)` → every movement with reference and person.
  - `open_requests_report(filters)` and `unverified_payments_report(filters)`.
- [ ] Definitions to agree with the accountant and write into docstrings:
  - "Sales" = confirmed order totals by confirmation date (cancelled excluded, returns subtracted).
  - "Paid sales" = allocations dated in the period; "credit" = sales − paid.
  - Week = Monday–Sunday in Africa/Addis_Ababa.
- [ ] `apps/reports/excel.py` → one workbook per report, formatted headers, ETB number format, totals row, frozen header, auto column widths.
- [ ] Endpoints: `GET /api/v1/reports/{sales|payments|credit|stock|movements|open-requests|unverified-payments}/?...` returning JSON; add `&format=xlsx` to download Excel.
- [ ] Permission: salespeople get only their own sales summary; storekeepers get Pawlos stock and movements; Personal-account figures are hidden unless the user has the `view_personal_payments` permission.

### 4.4 Scheduled jobs (Celery beat)

The schedule goes in `app.conf.beat_schedule` in `config/celery.py`.

| Task | Lives in | Schedule (Addis Ababa) | Action |
| --- | --- | --- | --- |
| `send_pending_notifications` | `apps/notifications/tasks.py` | every 15 s | Outbox → Telegram |
| `check_low_stock(product_id)` | `apps/inventory/tasks.py` | on each movement | If total available ≤ `min_stock`, notify once per day per product |
| `daily_report` | `apps/reports/tasks.py` | 20:00 every day | Text summary to admins |
| `weekly_report` | `apps/reports/tasks.py` | Saturday 20:00 | Text summary + Excel file |
| `monthly_report` | `apps/reports/tasks.py` | 1st of month 08:00 | Text summary + Excel file |
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
Top products: VC-001 ×20, OC-014 ×8, DS-003 ×4
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
- [ ] Low-stock alert fires once per day, not on every movement.

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
- **Branches:** `feature/<phase>-<task>` → PR into `develop` → staging; `develop` → `main` on each phase gate → production.

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
| `MAX_SALESPERSON_DISCOUNT_PCT` | `0` | api |
| `BACKUP_BUCKET_URL` | `s3://erp-backups` | backup job |
