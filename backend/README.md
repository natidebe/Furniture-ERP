# Furniture ERP Backend

Django REST Framework backend for an office furniture importer: multi-location stock, Pawlos
stock requests, sales orders with delivery notes, Organization/Personal payments, customer
credit, reports, and a Telegram bot.

**Stack:** Python 3.12 · Django 5.1 · DRF · PostgreSQL 16 · Celery + Redis · aiogram 3

## Documentation

- `BUILD_PHASES.md` — what to build, phase by phase
- `FOLDER_STRUCTURE.md` — where each piece lives

## First run (Docker)

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python manage.py makemigrations   # first run only, then commit
docker compose exec api python manage.py migrate
docker compose exec api python manage.py createsuperuser
```

- Health check: http://localhost:8000/health/
- API docs: http://localhost:8000/api/schema/swagger-ui/

## Try it with demo data

```bash
docker compose exec api python manage.py seed_demo
```

This creates one user per role (password `Demo-pass-2026`): `admin`, `accountant`,
`sales_pia` (Piassa), `sales_den` (Denbel), `store_paw` (Pawlos), five products with stock,
and one open stock request. It only runs with DEBUG on.

1. Open http://localhost:8000/api/schema/swagger-ui/
2. `POST /api/v1/auth/token/` with a username and password; copy the `access` token
3. Click **Authorize**, paste the token, and try the endpoints as that user
4. Log in as another user to see what each role can and cannot do

The Django admin is at http://localhost:8000/admin/ (log in as `admin`).
Check that stock balances match the ledger at any time:

```bash
docker compose exec api python manage.py rebuild_stock_balances --check
```

Run the tests against Postgres:

```bash
docker compose exec api pytest
```

## First run (local Python)

Needs Python 3.12, plus Postgres and Redis (`docker compose up -d db redis` is enough).

```bash
python3.12 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements/dev.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## Checks

```bash
ruff check .
pytest
python manage.py makemigrations --check --dry-run
```

## License

Proprietary. All rights reserved.
