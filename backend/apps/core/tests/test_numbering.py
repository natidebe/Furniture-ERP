import datetime
import threading

import pytest
from django.db import connection, transaction

from apps.core import numbering
from apps.core.models import DocumentSequence
from apps.core.numbering import next_number


def _in_year(monkeypatch, year):
    monkeypatch.setattr(numbering.timezone, "localdate", lambda: datetime.date(year, 6, 1))


@pytest.mark.django_db
def test_numbers_are_sequential_per_prefix(monkeypatch):
    _in_year(monkeypatch, 2026)
    with transaction.atomic():
        numbers = [next_number("SO") for _ in range(3)]
        other = next_number("PAY")

    assert numbers == ["SO-2026-00001", "SO-2026-00002", "SO-2026-00003"]
    assert other == "PAY-2026-00001"


@pytest.mark.django_db
def test_numbering_restarts_each_year(monkeypatch):
    _in_year(monkeypatch, 2026)
    with transaction.atomic():
        next_number("SO")
        next_number("SO")

    _in_year(monkeypatch, 2027)
    with transaction.atomic():
        assert next_number("SO") == "SO-2027-00001"


@pytest.mark.django_db
def test_rolled_back_number_is_reused(monkeypatch):
    """Gapless: a failed transaction does not burn a number."""
    _in_year(monkeypatch, 2026)
    with pytest.raises(RuntimeError), transaction.atomic():
        next_number("SO")
        raise RuntimeError

    with transaction.atomic():
        assert next_number("SO") == "SO-2026-00001"


@pytest.mark.django_db(transaction=True)
def test_requires_transaction():
    with pytest.raises(RuntimeError):
        next_number("SO")


@pytest.mark.django_db(transaction=True)
def test_parallel_callers_get_unique_numbers():
    if connection.vendor != "postgresql":
        pytest.skip("needs Postgres row locks")

    results, errors = [], []
    barrier = threading.Barrier(10)

    def worker():
        try:
            barrier.wait()
            with transaction.atomic():
                results.append(next_number("SO"))
        except Exception as exc:  # collected and asserted below
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(set(results)) == 10
    assert DocumentSequence.objects.get(prefix="SO").last_number == 10
