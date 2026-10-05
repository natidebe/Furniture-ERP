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
