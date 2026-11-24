from fastapi import HTTPException
from datetime import date
from sqlalchemy import select,or_
from app.models.boarding import Property,PropertyServicePrice,Room,Contract,UtilityReading,UtilityPriceHistory,Invoice,InvoiceUtilitySnapshot
from app.services.access_scope import assert_can_operate,get_contract,get_room,property_of_room,get_property
from app.services.dated_utility_pricing import DatedPrice, PricingBlocked, calculate_dated_charge
from app.services.db_util import save
from app.services.service_assignment_service import get_effective_services


def create_price(db,user,data):
    prop=get_property(db,data.property_id);assert_can_operate(db,user,prop)
    # One property lock serializes overlapping submissions and invoice issuance.
    db.scalar(select(Property).where(Property.id==prop.id).with_for_update())
    if data.room_id is not None and get_room(db,data.room_id).property_id!=prop.id: raise HTTPException(422,'Phòng không thuộc cơ sở.')
    if data.contract_id is not None:
        contract=get_contract(db,data.contract_id)
        if get_room(db,contract.room_id).property_id!=prop.id: raise HTTPException(422,'Hợp đồng không thuộc cơ sở.')
    issued=select(Invoice.id).join(Contract,Invoice.contract_id==Contract.id).join(Room,Contract.room_id==Room.id).where(Room.property_id==prop.id,Invoice.period>=data.valid_from.strftime('%Y-%m'),Invoice.period<=data.valid_to.strftime('%Y-%m'))
    if data.room_id is not None: issued=issued.where(Room.id==data.room_id)
    if data.contract_id is not None: issued=issued.where(Contract.id==data.contract_id)
    if db.scalar(issued.limit(1).with_for_update()) is not None: raise HTTPException(409,'Khoảng giá ảnh hưởng hóa đơn đã phát hành.')
    conditions=[UtilityPriceHistory.property_id==prop.id,UtilityPriceHistory.utility==data.utility,UtilityPriceHistory.room_id==data.room_id,UtilityPriceHistory.contract_id==data.contract_id,UtilityPriceHistory.valid_from<=data.valid_to,UtilityPriceHistory.valid_to>=data.valid_from]
    if db.scalar(select(UtilityPriceHistory.id).where(*conditions).with_for_update()) is not None: raise HTTPException(409,'Khoảng hiệu lực bị chồng lấn.')
    item=UtilityPriceHistory(**data.model_dump(),created_by=user.id);db.add(item);save(db,item)
    return serialize_price(item)


def serialize_price(item):
    return {'id':item.id,'property_id':item.property_id,'room_id':item.room_id,'contract_id':item.contract_id,'utility':item.utility,'unit_price':item.unit_price,'valid_from':item.valid_from,'valid_to':item.valid_to,'evidence':item.evidence,'created_by':item.created_by,'created_at':item.created_at}


def list_prices(db,user,property_id):
    prop=get_property(db,property_id);assert_can_operate(db,user,prop)
    return [serialize_price(x) for x in db.scalars(select(UtilityPriceHistory).where(UtilityPriceHistory.property_id==property_id).order_by(UtilityPriceHistory.id))]


def calculate(db,user,contract_id,period,lock=False):
    contract=get_contract(db,contract_id);room=get_room(db,contract.room_id);prop=property_of_room(db,room);assert_can_operate(db,user,prop)
    if lock: db.scalar(select(Property).where(Property.id==prop.id).with_for_update())
    try:
        first=date.fromisoformat(period+'-01')
        import calendar
        last=date(first.year,first.month,calendar.monthrange(first.year,first.month)[1])
    except (ValueError,TypeError): raise HTTPException(422,'Kỳ không hợp lệ.')
    if contract.status!='active' or contract.start_date>last or contract.end_date<first:raise HTTPException(409,'Hợp đồng không có hiệu lực trong kỳ.')
    query=select(UtilityPriceHistory).where(UtilityPriceHistory.property_id==prop.id,or_(UtilityPriceHistory.contract_id==contract.id,UtilityPriceHistory.room_id==room.id,(UtilityPriceHistory.contract_id.is_(None)&UtilityPriceHistory.room_id.is_(None))))
    if lock:query=query.with_for_update()
    candidates=[DatedPrice(x.id,'contract' if x.contract_id else 'room' if x.room_id else 'property',x.utility,x.unit_price,x.valid_from,x.valid_to) for x in db.scalars(query)]
    effective_services={item.service_code.value:item for item in get_effective_services(db,contract)}
    service_prices={row.service_code:row for row in db.scalars(select(PropertyServicePrice).where(
        PropertyServicePrice.property_id==prop.id,
        PropertyServicePrice.service_code.in_(('electricity','water')),
    ))}
    query=select(UtilityReading).where(UtilityReading.room_id==room.id,UtilityReading.period==period)
    if lock:query=query.with_for_update()
    readings={x.utility_type:x for x in db.scalars(query)};results=[]
    for kind in ('electricity','water'):
        reading=readings.get(kind)
        if reading is None:raise HTTPException(409,'Thiếu chỉ số '+kind+' trong kỳ.')
        configured=service_prices.get(kind)
        assignment=effective_services.get(kind)
        if assignment is not None and assignment.billing_unit is not None:
            expected_unit='kwh' if kind=='electricity' else 'm3'
            if assignment.billing_unit.value!=expected_unit:
                raise HTTPException(409,'Đơn vị cấu hình dịch vụ '+kind+' phải là '+expected_unit+'.')
        unit_price=(assignment.effective_price if assignment is not None else None)
        source=(assignment.source if assignment is not None else 'service_config')
        if unit_price is None and configured is not None:
            unit_price=configured.unit_price
            if configured.billing_unit!=('kwh' if kind=='electricity' else 'm3'):
                raise HTTPException(409,'Đơn vị cấu hình dịch vụ '+kind+' phải là '+('kwh' if kind=='electricity' else 'm3')+'.')
            source='service_config'
        price_id=None
        valid_from=None
        valid_to=None
        if unit_price is None:
            # Keep existing dated prices usable for older properties while new
            # calculations use the shared service-price configuration.
            try: charge=calculate_dated_charge(period,kind,reading.previous_reading,reading.current_reading,candidates)
            except PricingBlocked as exc:
                reasons={'No effective price for the entire period':'Chưa cấu hình đơn giá dịch vụ hoặc giá có hiệu lực toàn kỳ','Overlapping prices at the same priority':'Các khoảng giá cùng cấp bị chồng lấn','Price changes during period; allocation is not approved':'Giá thay đổi giữa kỳ; chưa có quy tắc phân bổ','Meter reset or replacement requires an approved rule':'Chỉ số giảm hoặc thay công tơ chưa có quy tắc'}
                raise HTTPException(409,'Không thể tính '+kind+': '+reasons.get(str(exc),str(exc))) from exc
            unit_price=charge.price.unit_price
            source=charge.price.scope
            price_id=charge.price.record_id
            valid_from=charge.price.valid_from
            valid_to=charge.price.valid_to
        consumption=reading.current_reading-reading.previous_reading
        if unit_price<0 or consumption*unit_price>2_147_483_647:
            raise HTTPException(422,'Không thể tính '+kind+': thành tiền vượt giới hạn lưu trữ.')
        results.append({'utility':kind,'previous_reading':reading.previous_reading,'current_reading':reading.current_reading,'consumption':consumption,'unit_price':unit_price,'source':source,'price_id':price_id,'valid_from':valid_from,'valid_to':valid_to,'amount':consumption*unit_price})
    fixed_total=0;fixed_items=[]
    for service in effective_services.values():
        if service.service_code.value in {'electricity','water'}:
            expected_unit='kwh' if service.service_code.value=='electricity' else 'm3'
            if service.billing_unit is not None and service.billing_unit.value!=expected_unit:
                raise HTTPException(409,'Đơn vị điện/nước không phù hợp cách tính chỉ số đã duyệt.')
            continue
        if service.effective_price is None or service.billing_unit is None:
            raise HTTPException(409,f'Chưa cấu hình giá/đơn vị cho {service.service_name}.')
        if service.billing_unit.value in {'kwh','m3'}:
            raise HTTPException(409,'Đơn vị dịch vụ biến đổi chưa được hỗ trợ.')
        amount=service.quantity*service.effective_price
        fixed_total+=amount
        fixed_items.append({'service_code':service.service_code.value,'source':service.source,'quantity':service.quantity,'unit_price':service.effective_price,'billing_unit':service.billing_unit.value,'amount':amount})
    total=sum(x['amount'] for x in results)
    if total+fixed_total+contract.monthly_rent>2147483647:raise HTTPException(422,'Tổng tiền vượt giới hạn lưu trữ.')
    return {'property_id':prop.id,'room_id':room.id,'contract_id':contract.id,'period':period,'items':results,'total':total,'fixed_items':fixed_items,'fixed_service_total':fixed_total,'invoice_utility_total':total+fixed_total,'rent_amount':contract.monthly_rent,'invoice_total':contract.monthly_rent+total+fixed_total}
