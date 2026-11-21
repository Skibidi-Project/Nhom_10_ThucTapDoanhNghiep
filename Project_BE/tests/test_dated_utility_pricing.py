from datetime import date
import pytest
from app.services.dated_utility_pricing import DatedPrice, PricingBlocked, calculate_dated_charge, resolve_dated_price


def price(record_id, scope, value, start='2026-01-01', end=None, utility='electricity'):
    return DatedPrice(record_id, scope, utility, value, date.fromisoformat(start), date.fromisoformat(end) if end else None)


def test_approved_precedence_and_fallback():
    contract, room, prop = price(1,'contract',4000), price(2,'room',3800), price(3,'property',3500)
    assert resolve_dated_price('2026-02','electricity',[prop,room,contract]) == contract
    assert resolve_dated_price('2026-02','electricity',[prop,room]) == room
    assert resolve_dated_price('2026-02','electricity',[prop]) == prop
    assert resolve_dated_price('2026-02','electricity',[room]) == room
    assert resolve_dated_price('2026-02','electricity',[contract]) == contract
    assert 100 * resolve_dated_price('2026-02','electricity',[prop,room,contract]).unit_price == 400000


def test_different_utilities_and_zero_price():
    electric=price(1,'contract',4000); water=price(2,'property',0,utility='water')
    assert resolve_dated_price('2026-02','electricity',[electric,water]) == electric
    assert resolve_dated_price('2026-02','water',[electric,water]) == water


def test_expired_future_and_missing_history():
    p=price(1,'property',3500);expired=price(2,'contract',4000,end='2026-01-31');future=price(3,'room',3800,start='2026-03-01')
    assert resolve_dated_price('2026-02','electricity',[p,expired,future]) == p
    with pytest.raises(PricingBlocked):resolve_dated_price('2026-02','electricity',[expired,future])
    with pytest.raises(PricingBlocked):resolve_dated_price('2026-02','water',[p])


def test_mid_period_change_or_gap_is_blocked():
    prop=price(1,'property',3500);partial=price(2,'contract',4000,start='2026-02-15')
    with pytest.raises(PricingBlocked,match='changes'):resolve_dated_price('2026-02','electricity',[prop,partial])
    with pytest.raises(PricingBlocked,match='entire'):resolve_dated_price('2026-02','electricity',[price(3,'property',1,start='2026-02-02')])
    with pytest.raises(PricingBlocked,match='changes'):resolve_dated_price('2026-02','electricity',[price(4,'property',1,end='2026-02-14'),price(5,'property',1,start='2026-02-15')])


def test_overlap_invalid_and_unrelated_price():
    with pytest.raises(PricingBlocked,match='Overlapping'):resolve_dated_price('2026-02','electricity',[price(1,'contract',1),price(2,'contract',2)])
    with pytest.raises(PricingBlocked,match='Invalid price'):resolve_dated_price('2026-02','electricity',[price(1,'property',-1)])
    with pytest.raises(PricingBlocked,match='period'):resolve_dated_price('2026-13','electricity',[])
    assert resolve_dated_price('2026-02','electricity',[price(1,'contract',5),price(2,'property',1),price(3,'property',2)]).unit_price == 5


def test_calculation_zero_normal_reset_missing_and_overflow():
    candidates=[price(1,'contract',4000)]
    zero=calculate_dated_charge('2026-02','electricity',100,100,candidates)
    assert zero.consumption==0 and zero.amount==0 and zero.price.scope=='contract'
    result=calculate_dated_charge('2026-02','electricity',100,200,candidates)
    assert result.consumption==100 and result.amount==400000
    with pytest.raises(PricingBlocked,match='reset'):calculate_dated_charge('2026-02','electricity',200,100,candidates)
    with pytest.raises(PricingBlocked,match='readings'):calculate_dated_charge('2026-02','electricity',None,100,candidates)
    with pytest.raises(PricingBlocked,match='entire'):calculate_dated_charge('2026-02','electricity',100,100,[])
    with pytest.raises(PricingBlocked,match='storage'):calculate_dated_charge('2026-02','electricity',0,1000000,candidates)
