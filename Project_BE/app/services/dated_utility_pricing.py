"""US-20 dated price selection; not wired to billing until history exists.

Callers must first scope all candidates to the authorized contract/room/property.
A period is chargeable only when one unambiguous effective record covers it.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Sequence

Scope = Literal['contract', 'room', 'property']
PRIORITY = {'contract': 0, 'room': 1, 'property': 2}

class PricingBlocked(ValueError):
    """The configured history cannot establish one valid price for the period."""

@dataclass(frozen=True)
class DatedPrice:
    record_id: int
    scope: Scope
    utility: Literal['electricity', 'water']
    unit_price: int
    valid_from: date
    valid_to: date | None = None


@dataclass(frozen=True)
class UtilityCharge:
    utility: str
    previous_reading: int
    current_reading: int
    consumption: int
    price: DatedPrice
    amount: int


def resolve_dated_price(period: str, utility: str, prices: Sequence[DatedPrice]) -> DatedPrice:
    """Pick contract > room > property for every day of a calendar month.

    Intervals are inclusive. Missing history, same-level overlapping records or
    a change of the selected record during the month are rejected. This does
    not invent a method for splitting consumption across rate changes.
    """
    try:
        if len(period) != 7 or period[4] != '-' or not (period[:4]+period[5:]).isdigit():
            raise ValueError
        year, month = int(period[:4]), int(period[5:])
        first = date(year, month, 1)
        last = date(year, month, monthrange(year, month)[1])
    except (ValueError, TypeError, OverflowError):
        raise PricingBlocked('Invalid billing period') from None
    if utility not in {'electricity', 'water'}:
        raise PricingBlocked('Invalid utility')
    candidates = []
    for item in prices:
        if item.utility != utility:
            continue
        if item.scope not in PRIORITY or isinstance(item.unit_price, bool) or not isinstance(item.unit_price, int) or item.unit_price < 0 or item.record_id <= 0:
            raise PricingBlocked('Invalid price record')
        if not isinstance(item.valid_from, date) or (item.valid_to is not None and (not isinstance(item.valid_to, date) or item.valid_to < item.valid_from)):
            raise PricingBlocked('Invalid price validity')
        if item.valid_from <= last and (item.valid_to is None or item.valid_to >= first):
            candidates.append(item)
    points = {first}
    for item in candidates:
        if first < item.valid_from <= last:
            points.add(item.valid_from)
        if item.valid_to is not None and first <= item.valid_to < last:
            points.add(item.valid_to + timedelta(days=1))
    chosen = []
    for day in sorted(points):
        active = [p for p in candidates if p.valid_from <= day and (p.valid_to is None or day <= p.valid_to)]
        if not active:
            raise PricingBlocked('No effective price for the entire period')
        rank = min(PRIORITY[p.scope] for p in active)
        best = [p for p in active if PRIORITY[p.scope] == rank]
        if len(best) != 1:
            raise PricingBlocked('Overlapping prices at the same priority')
        chosen.append(best[0])
    if any(p != chosen[0] for p in chosen[1:]):
        raise PricingBlocked('Price changes during period; allocation is not approved')
    return chosen[0]


def calculate_dated_charge(period: str, utility: str, previous: int, current: int, prices: Sequence[DatedPrice]) -> UtilityCharge:
    """Calculate only when readings and dated pricing are both unambiguous."""
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (previous, current)):
        raise PricingBlocked('Meter readings must be non-negative integers')
    if current < previous:
        raise PricingBlocked('Meter reset or replacement requires an approved rule')
    price = resolve_dated_price(period, utility, prices)
    consumption = current - previous
    amount = consumption * price.unit_price
    if amount > 2_147_483_647:
        raise PricingBlocked('Calculated amount exceeds supported storage')
    return UtilityCharge(utility, previous, current, consumption, price, amount)
