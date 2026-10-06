FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Pango/HarfBuzz for WeasyPrint (delivery note PDFs) and an Ethiopic font for Ethiopian
# dates on them; postgresql-client for pg_dump/dbshell.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
        fonts-sil-abyssinica \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ARG REQUIREMENTS=base.txt
COPY requirements/ requirements/
COPY bot/requirements.txt bot/requirements.txt
RUN pip install -r requirements/${REQUIREMENTS}

COPY . .

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
