# Furniture ERP Backend — Folder Structure

The complete directory layout for the project. It matches `BUILD_PHASES.md`. If the two disagree, `BUILD_PHASES.md` wins; update this file to match it.

The skeleton is already created. Files for later phases are empty placeholders. The settings, health endpoint and placeholder `User` model are filled in, so the project runs from day one.

```
Furniture-ERP/                          # repository root
├── .github/workflows/ci.yml            # ruff → makemigrations --check → pytest (Postgres) → docker build
│                                       # (runs inside backend/)
├── BUILD_PHASES.md
├── FOLDER_STRUCTURE.md
└── backend/                            # tree below
```

```
backend/
│
├── config/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                   # Shared: apps, middleware, DB, DRF, JWT, axes, Celery
│   │   ├── dev.py                    # DEBUG, open CORS, dev secret key
│   │   └── prod.py                   # HTTPS, security headers, Sentry
│   ├── __init__.py                   # Loads the Celery app
│   ├── urls.py                       # /admin/, /health/, /api/schema/, /api/v1/...
│   ├── celery.py                     # Celery app + beat schedule (Phase 4.4)
│   ├── wsgi.py
│   └── asgi.py
│
├── apps/
│   ├── __init__.py
│   │
│   ├── core/                         # Phase 1 — shared base pieces
│   │   ├── models.py                 # TimeStampedModel, ActiveModel, DocumentSequence
│   │   ├── numbering.py              # next_number("SO") → SO-2026-00125
│   │   ├── exceptions.py             # BusinessRuleError + DRF exception handler
│   │   ├── views.py                  # GET /health/
│   │   └── tests/
│   │       ├── test_health.py
│   │       └── test_numbering.py
│   │
│   ├── accounts/                     # Phase 1 — users, roles, Telegram linking
│   │   ├── models.py                 # User, Role, ERPPermission, ROLE_DEFAULT_PERMISSIONS, TelegramLinkToken
│   │   ├── permissions.py            # Role classes + erp_permission(...) for per-user permissions
│   │   ├── authentication.py         # BotUserAuthentication (Phase 4)
│   │   ├── signals.py                # Keeps the Django Group in sync with User.role
│   │   ├── services.py               # create_link_code(), link_telegram()
│   │   ├── selectors.py
│   │   ├── tasks.py                  # expire_link_tokens (Phase 4)
│   │   └── api/                      # /auth/token/, /auth/refresh/, /auth/me/,
│   │                                 # /auth/telegram/link-code/, /auth/telegram/link/, /users/,
│   │                                 # /permissions/
│   │
│   ├── locations/                    # Phase 1 — Piassa, Piassa Underground, Denbel, Pawlos, TRANSIT
│   │   ├── models.py                 # Location
│   │   ├── services.py
│   │   ├── selectors.py
│   │   └── api/                      # /locations/
│   │
│   ├── catalog/                      # Phase 1 — products and prices (no cost price)
│   │   ├── models.py                 # Category, Unit, Product, PriceHistory
│   │   ├── services.py               # change_price()
│   │   ├── selectors.py
│   │   ├── management/commands/
│   │   │   └── import_products.py
│   │   └── api/                      # /products/, /products/{id}/change-price/, /categories/, /units/
│   │
│   ├── audit/                        # Phase 1 — audit log
│   │   ├── models.py                 # AuditLog
│   │   ├── services.py               # audit_log()
│   │   ├── selectors.py
│   │   ├── middleware.py             # Stores request IP and source (web / bot) for audit_log()
│   │   └── api/                      # /audit/ (accountant read, admin)
│   │
│   ├── customers/                    # Model in Phase 2; endpoints and selectors in Phase 3
│   │   ├── models.py                 # Customer
│   │   ├── services.py
│   │   ├── selectors.py              # customer_balance(), customer_statement()
│   │   ├── management/commands/
│   │   │   └── import_customers.py
│   │   └── api/                      # /customers/, /customers/{id}/balance/, /customers/{id}/statement/
│   │
│   ├── inventory/                    # Phase 2 — stock ledger
│   │   ├── models.py                 # StockMovement, StockBalance, GoodsReceipt(+Line),
│   │   │                             # StockAdjustment, StockTransfer(+Line)
│   │   ├── services.py               # post_movement(), reserve(), unreserve(), reverse_movement(),
│   │   │                             # receive_goods(), propose/approve_adjustment(),
│   │   │                             # send_transfer(), receive_transfer()
│   │   ├── selectors.py
│   │   ├── tasks.py                  # check_low_stock (stub in Phase 2), nightly_stock_check
│   │   ├── management/commands/
│   │   │   ├── rebuild_stock_balances.py
│   │   │   └── import_opening_stock.py
│   │   └── api/                      # /stock/, /stock/summary/, /stock/movements/,
│   │                                 # /products/{id}/stock/, /goods-receipts/, /adjustments/,
│   │                                 # /transfers/
│   │
│   ├── requests/                     # Phase 2 — Pawlos stock requests and releases
│   │   ├── models.py                 # StockRequest(+Line), StockRelease(+Line)
│   │   ├── services.py               # create_stock_request(), acknowledge_request(),
│   │   │                             # release_stock(), reject_request(), cancel_request()
│   │   ├── selectors.py
│   │   └── api/                      # /stock-requests/ (+ acknowledge, release, reject, cancel)
│   │
│   ├── sales/                        # Phase 3 — orders and delivery notes
│   │   ├── models.py                 # SalesOrder(+Line), DeliveryNote(+Line)
│   │   ├── services.py               # create_order(), confirm_order(), release_from_branch(),
│   │   │                             # cancel_order(), return_goods(), void_order(), ...
│   │   ├── selectors.py
│   │   ├── pdf.py                    # Delivery note PDF (WeasyPrint)
│   │   ├── templates/sales/
│   │   │   └── delivery_note.html
│   │   ├── management/commands/
│   │   │   └── import_opening_balances.py
│   │   └── api/                      # /orders/ (+ confirm, release-from-branch, status, cancel,
│   │                                 # return, void, history, payments, delivery-note.pdf)
│   │
│   ├── payments/                     # Phase 3 — Organization / Personal payments
│   │   ├── models.py                 # PaymentAccount, Payment, PaymentAllocation
│   │   ├── services.py               # record_payment(), allocate_payment(), allocate_oldest_first(),
│   │   │                             # verify/reject/reverse/correct_payment(), refresh_payment_status()
│   │   ├── selectors.py              # order_paid(), order_remaining(), line_paid(), ...
│   │   └── api/                      # /payments/ (+ allocate, verify, reject, reverse, correct),
│   │                                 # /payment-accounts/
│   │
│   ├── reports/                      # Search + history in Phase 3; reports in Phase 4. Read-only
│   │   ├── models.py                 # (empty)
│   │   ├── selectors.py              # sales_report(), payments_report(), credit_report(), ...
│   │   ├── search.py                 # search() across products, customers, orders, DN, SR, payments
│   │   ├── history.py                # transaction_history(): full timeline from any related number
│   │   ├── excel.py                  # One openpyxl workbook per report
│   │   ├── tasks.py                  # daily_report, weekly_report, monthly_report, yearly_report
│   │   └── api/                      # /reports/{sales|payments|credit|stock|movements|
│   │                                 # open-requests|unverified-payments}/ (?format=xlsx),
│   │                                 # /search/, /transactions/{number}/
│   │
│   └── notifications/                # notify() stub in Phase 2; outbox in Phase 4. No endpoints.
│       ├── models.py                 # NotificationOutbox
│       ├── services.py               # notify() — writes outbox rows in the caller's transaction
│       ├── selectors.py
│       ├── tasks.py                  # send_pending_notifications
│       ├── telegram.py               # Plain HTTPS calls to the Telegram Bot API
│       └── templates.py              # Message formats shared by API notifications and the bot
│
├── bot/                              # Phase 4 — aiogram 3 webhook service; talks only to the API
│   ├── __init__.py
│   ├── main.py                       # aiohttp webhook app, dispatcher setup
│   ├── config.py                     # BOT_TOKEN, WEBHOOK_SECRET, API_BASE_URL, BOT_SERVICE_TOKEN
│   ├── api_client.py                 # httpx client; sends X-Telegram-User and X-Client: bot
│   ├── keyboards.py                  # Role-based menus, inline buttons
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py                  # /start <code> linking, main menu
│   │   ├── search.py                 # Free text → product lookup (e.g. VC-001)
│   │   ├── storekeeper.py            # Requests list, acknowledge, release flow
│   │   ├── salesperson.py            # Check stock, my orders, my sales, stock request
│   │   └── accountant.py             # Payments to verify, quick report
│   ├── requirements.txt              # aiogram, aiohttp, httpx, sentry-sdk
│   └── Dockerfile                    # Added in Phase 4
│
├── requirements/
│   ├── base.txt                      # Runtime (API, worker, beat)
│   └── dev.txt                       # -r base.txt + pytest, pytest-cov, factory-boy, ruff, mypy, ...
│
├── tests/                            # Cross-app tests
│   ├── __init__.py
│   ├── factories.py                  # factory_boy factories for all models
│   └── test_flows.py                 # Walk-in, Pawlos and phone-order flows end to end
│
├── conftest.py                       # Shared pytest fixtures (visible to apps/ and tests/)
├── docker-compose.yml                # db, redis, api, worker, beat (+ bot in Phase 4)
├── Dockerfile                        # API / worker / beat image (includes WeasyPrint libraries)
├── .dockerignore
├── .env.example                      # Every variable from BUILD_PHASES.md Appendix B
├── .gitignore
├── manage.py
├── pytest.ini
├── ruff.toml
├── mypy.ini
└── README.md
```

Every app also has `__init__.py`, `apps.py`, `admin.py`, `migrations/__init__.py` and `tests/__init__.py`. They are left out above to keep the tree readable.

---

## Per-app layout

Every app follows the conventions in `BUILD_PHASES.md` Appendix A:

```
app_name/
├── migrations/
├── api/                  # serializers.py, views.py, urls.py
├── management/commands/  # only where an import or check command exists
├── models.py
├── services.py           # writes and business rules
├── selectors.py          # reads
├── tasks.py              # Celery tasks, only where needed
├── admin.py
├── apps.py
└── tests/
```

Exceptions:

- `core` has no `api/`, `services.py` or `selectors.py`. It holds `numbering.py`, `exceptions.py` and the health view.
- `reports` is read-only, so it has no `services.py`.
- `notifications` has no `api/`. Staff see notifications in Telegram, or in the web app via the other endpoints.

| Layer | File | Responsibility |
|-------|------|----------------|
| Data | `models.py` | Fields, constraints, indexes. No business logic. |
| Writes | `services.py` | Every change and state transition. `transaction.atomic()`, `select_for_update()`, `audit_log()`. |
| Reads | `selectors.py` | Queries, balances, aggregations. Never writes. |
| REST | `api/serializers.py` | Input validation and output format only. |
| REST | `api/views.py` | Permissions, then one service or selector call. |
| REST | `api/urls.py` | Included under `/api/v1/` in `config/urls.py`. |
| Jobs | `tasks.py` | Celery tasks; they call services and selectors. |
| Tests | `tests/` | Per-app tests. Shared fixtures in the root `conftest.py`, factories in `tests/factories.py`. |

Role permission classes live in `apps/accounts/permissions.py` and are imported by every app's views.

---

## Migration order

All 12 apps are in `INSTALLED_APPS` from day one. Their models are added phase by phase:

1. **Phase 1:** `core`, `accounts`, `locations`, `catalog`, `audit`. Run `makemigrations` for `accounts` and `locations` together. `User.home_location` → `Location` and `Location.created_by` → `User` point at each other, and Django splits this circular dependency only when it generates both at once.
2. **Phase 2:** `customers` (the `Customer` model and the walk-in customer, because movements and requests reference customers), then `inventory` (including the TRANSIT location data migration), then `requests`. `notifications` gets only the no-op `notify()` stub and no models yet.
3. **Phase 3:** `sales`, `payments`, plus follow-up migrations that add `StockRequest.order` and `User.allowed_payment_accounts`.
4. **Phase 4:** `notifications` (`NotificationOutbox`). `reports` has no models.
5. **Phase 5:** no schema changes. Real data is loaded with the import management commands.

---

## First run

```bash
cd backend
cp .env.example .env
docker compose up -d --build
docker compose exec api python manage.py makemigrations   # first run only; commit the result
docker compose exec api python manage.py migrate
```

Then open `http://localhost:8000/health/` and `/api/schema/swagger-ui/`, and start Phase 1 in `BUILD_PHASES.md`.
