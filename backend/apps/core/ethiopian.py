"""The Ethiopian calendar (Q12, owner's answer 6 Oct 2026): dates are shown Ethiopian first
with the Gregorian date beside them, and report months and years are Ethiopian.

Twelve months of 30 days, then Pagume with 5 days (6 in the year before a Gregorian leap
year, i.e. when the Ethiopian year % 4 == 3). Conversion goes through the Julian day number
(Amete Mihret era).
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.utils import timezone

_EPOCH = 1723856           # Amete Mihret offset used by the standard JDN formulas
_ORDINAL_TO_JDN = 1721425  # date.toordinal() + this = Julian day number

MONTHS_AM = ["መስከረም", "ጥቅምት", "ኅዳር", "ታኅሣሥ", "ጥር", "የካቲት", "መጋቢት", "ሚያዝያ",
             "ግንቦት", "ሰኔ", "ሐምሌ", "ነሐሴ", "ጳጉሜ"]
MONTHS_EN = ["Meskerem", "Tikimt", "Hidar", "Tahsas", "Tir", "Yekatit", "Megabit", "Miyazya",
             "Ginbot", "Sene", "Hamle", "Nehase", "Pagume"]


@dataclass(frozen=True, order=True)
class EthiopianDate:
    year: int
    month: int  # 1–13
    day: int

    def __str__(self) -> str:
        return f"{MONTHS_AM[self.month - 1]} {self.day}, {self.year}"

    @property
    def month_name(self) -> str:
        return MONTHS_AM[self.month - 1]

    def to_gregorian(self) -> date:
        return to_gregorian(self.year, self.month, self.day)


def is_leap(year: int) -> bool:
    """An Ethiopian leap year has a 6-day Pagume."""
    return year % 4 == 3


def month_length(year: int, month: int) -> int:
    if month < 13:
        return 30
    return 6 if is_leap(year) else 5


def to_ethiopian(value: date | datetime) -> EthiopianDate:
    if isinstance(value, datetime):
        value = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    jdn = value.toordinal() + _ORDINAL_TO_JDN
    r = (jdn - _EPOCH) % 1461
    n = r % 365 + 365 * (r // 1460)
    year = 4 * ((jdn - _EPOCH) // 1461) + r // 365 - r // 1460
    return EthiopianDate(year, n // 30 + 1, n % 30 + 1)


def to_gregorian(year: int, month: int, day: int) -> date:
    if not 1 <= month <= 13 or not 1 <= day <= month_length(year, month):
        raise ValueError(f"No such Ethiopian date: {year}-{month}-{day}.")
    jdn = (_EPOCH + 365) + 365 * (year - 1) + year // 4 + 30 * month + day - 31
    return date.fromordinal(jdn - _ORDINAL_TO_JDN)


def month_range(year: int, month: int) -> tuple[date, date]:
    """First and last Gregorian day of an Ethiopian month."""
    return to_gregorian(year, month, 1), to_gregorian(year, month, month_length(year, month))


def year_range(year: int) -> tuple[date, date]:
    """Meskerem 1 to the last day of Pagume."""
    return to_gregorian(year, 1, 1), to_gregorian(year, 13, month_length(year, 13))


def format_ec(value: date | datetime | None) -> str:
    """"ጥቅምት 26, 2019"."""
    return str(to_ethiopian(value)) if value is not None else ""


def format_both(value: date | datetime | None, *, with_time: bool = False) -> str:
    """Ethiopian first, Gregorian beside it: "ጥቅምት 26, 2019 (05/11/2026)"."""
    if value is None:
        return ""
    gregorian = value
    if isinstance(value, datetime) and timezone.is_aware(value):
        gregorian = timezone.localtime(value)
    text = f"{format_ec(value)} ({gregorian.strftime('%d/%m/%Y')})"
    if with_time and isinstance(gregorian, datetime):
        text += f" {gregorian.strftime('%H:%M')}"
    return text


def format_range(first: date, last: date) -> str:
    """A report period: one date, or "first – last" in both calendars."""
    if first == last:
        return format_both(first)
    return (f"{format_ec(first)} – {format_ec(last)} "
            f"({first.strftime('%d/%m/%Y')} – {last.strftime('%d/%m/%Y')})")


def month_label(year: int, month: int) -> str:
    return f"{MONTHS_AM[month - 1]} {year}"


def months_between(first: date, last: date) -> list[tuple[int, int]]:
    """Every Ethiopian (year, month) touching first..last, in order."""
    start, end = to_ethiopian(first), to_ethiopian(last)
    months, year, month = [], start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        month += 1
        if month > 13:
            year, month = year + 1, 1
    return months


def today() -> EthiopianDate:
    return to_ethiopian(timezone.localdate())


def previous_month(ec: EthiopianDate) -> tuple[int, int]:
    return (ec.year, ec.month - 1) if ec.month > 1 else (ec.year - 1, 13)


def add_days(value: date, days: int) -> date:
    return value + timedelta(days=days)
