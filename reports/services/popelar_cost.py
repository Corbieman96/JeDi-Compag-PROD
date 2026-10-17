from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from catalogs.models import DriverAbsence
from core.models import AppSettings
from reports.services.date_range import ReportDateRange

_TWO = Decimal("0.01")
_HALF = Decimal("0.5")


@dataclass(frozen=True)
class PopelarCostSummary:
    days: Decimal
    hours: Decimal
    hours_per_day: Decimal
    rate_czk: Decimal
    total_czk: Decimal


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(_TWO, rounding=ROUND_HALF_UP)


def _absence_days_in_range(absence: DriverAbsence, date_range: ReportDateRange) -> int:
    start = max(absence.date_from, date_range.date_from)
    end = min(absence.date_to, date_range.date_to)
    if end < start:
        return 0
    return (end - start).days + 1


def _popelar_day_units(absence: DriverAbsence, date_range: ReportDateRange) -> Decimal:
    days = _absence_days_in_range(absence, date_range)
    if days <= 0:
        return Decimal("0")
    units = Decimal(days)
    if absence.is_partial:
        units *= _HALF
    return units


def build_popelar_cost(date_range: ReportDateRange) -> PopelarCostSummary:
    settings = AppSettings.load()
    hours_per_day = Decimal(settings.popelar_hours_per_day or 0)
    rate_czk = Decimal(settings.popelar_hourly_rate_czk or 0)

    total_days = Decimal("0")
    abs_qs = DriverAbsence.objects.filter(
        absence_type=DriverAbsence.AbsenceType.GARBAGE,
        date_from__lte=date_range.date_to,
        date_to__gte=date_range.date_from,
    )
    for absence in abs_qs.iterator():
        total_days += _popelar_day_units(absence, date_range)

    hours = _quantize_money(total_days * hours_per_day)
    total_czk = _quantize_money(hours * rate_czk)
    return PopelarCostSummary(
        days=_quantize_money(total_days),
        hours=hours,
        hours_per_day=_quantize_money(hours_per_day),
        rate_czk=_quantize_money(rate_czk),
        total_czk=total_czk,
    )
