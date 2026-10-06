from datetime import date, timedelta

import pytest

from apps.core import ethiopian as ec


@pytest.mark.parametrize("gregorian,expected", [
    (date(2023, 9, 12), (2016, 1, 1)),   # New Year before a Gregorian leap year
    (date(2024, 9, 11), (2017, 1, 1)),
    (date(2025, 9, 11), (2018, 1, 1)),
    (date(2026, 9, 11), (2019, 1, 1)),
    (date(2025, 1, 7), (2017, 4, 29)),   # Genna (Ethiopian Christmas)
    (date(2023, 9, 11), (2015, 13, 6)),  # Pagume 6: 2015 was a leap year
    (date(2024, 9, 10), (2016, 13, 5)),  # Pagume 5 ends 2016
    (date(2025, 9, 10), (2017, 13, 5)),  # Pagume 5
    (date(2026, 10, 6), (2019, 1, 26)),
    (date(2026, 11, 5), (2019, 2, 26)),
    (date(1991, 5, 28), (1983, 9, 20)),
])
def test_known_dates(gregorian, expected):
    assert tuple(vars(ec.to_ethiopian(gregorian)).values()) == expected
    assert ec.to_gregorian(*expected) == gregorian


def test_every_day_for_twenty_years_round_trips_and_steps_by_one():
    day = date(2015, 1, 1)
    previous = ec.to_ethiopian(day - timedelta(days=1))
    for _ in range(366 * 20):
        current = ec.to_ethiopian(day)
        assert current.to_gregorian() == day
        if current.day == 1:  # first of a month: the previous day ended the last month
            assert previous.day == ec.month_length(previous.year, previous.month)
        else:
            assert (current.year, current.month, current.day - 1) == (
                previous.year, previous.month, previous.day)
        previous, day = current, day + timedelta(days=1)


def test_month_and_year_ranges():
    assert ec.month_range(2019, 2) == (date(2026, 10, 11), date(2026, 11, 9))
    assert ec.month_range(2016, 13) == (date(2024, 9, 6), date(2024, 9, 11 - 1))
    assert ec.year_range(2018) == (date(2025, 9, 11), date(2026, 9, 10))
    first, last = ec.year_range(2019)
    assert len(ec.months_between(first, last)) == 13


def test_invalid_dates_are_refused():
    with pytest.raises(ValueError):
        ec.to_gregorian(2017, 13, 6)  # 2017 is not a leap year
    with pytest.raises(ValueError):
        ec.to_gregorian(2019, 2, 31)


def test_formats_put_ethiopian_first():
    assert ec.format_ec(date(2026, 11, 5)) == "ጥቅምት 26, 2019"
    assert ec.format_both(date(2026, 11, 5)) == "ጥቅምት 26, 2019 (05/11/2026)"
    assert ec.format_range(date(2026, 10, 11), date(2026, 11, 9)) == (
        "ጥቅምት 1, 2019 – ጥቅምት 30, 2019 (11/10/2026 – 09/11/2026)")
    assert ec.month_label(2019, 13) == "ጳጉሜ 2019"
