"""Proposed US-16 workflow, strictly restricted to isolated test databases."""
import os
import tempfile
import calendar
import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import insert, select, update
from app.db.settlement_trial import damages, settlements, receivables, invoice_reviews, final_approvals, meter_handovers, input_revisions
from app.models.boarding import Contract, Invoice, Payment, Property, Room, UtilityReading
from app.services.access_scope import assert_can_operate, assert_can_manage, property_of_room
from app.services.db_util import save

def allowed(db):
    url=db.get_bind().url
    isolated_sqlite=url.get_backend_name()=='sqlite' and (url.database in (None,'',':memory:') or (Path(url.database).resolve().parent == Path(tempfile.gettempdir()).resolve() and Path(url.database).name.startswith('ministay_business_e2e_')))
    isolated_mysql=url.get_backend_name()=='mysql' and url.host in ('localhost','127.0.0.1') and (url.port or 3306)==3306 and (url.database or '').startswith('ministay_business_test_')
    return os.getenv('MINISTAY_US16_TRIAL')=='1' and (isolated_sqlite or isolated_mysql)

def require_trial(db):
    if not allowed(db):
        raise HTTPException(409,'Quyết toán thử nghiệm chỉ được phép trên database test cô lập.')

def locked_contract(db, user, contract_id):
    original=db.get(Contract,contract_id)
    if original is None: raise HTTPException(404,'Không tìm thấy hợp đồng.')
    room=db.scalar(select(Room).where(Room.id==original.room_id).with_for_update())
    if room is None: raise HTTPException(404,'Không tìm thấy phòng.')
    assert_can_operate(db,user,property_of_room(db,room))
    db.scalar(select(Property).where(Property.id==room.property_id).with_for_update().execution_options(populate_existing=True))
    contract=db.scalar(select(Contract).where(Contract.id==contract_id).with_for_update().execution_options(populate_existing=True))
    return contract,room

def approval_inputs(db, contract, room, start, end):
    from app.services.service_assignment_service import get_effective_services
    from app.db.reading_revision import reading_revision
    prop=property_of_room(db,room)
    period=start.strftime('%Y-%m')
    readings=db.scalars(select(UtilityReading).where(UtilityReading.room_id==room.id,UtilityReading.period==period).order_by(UtilityReading.id).with_for_update()).all()
    invoices=db.scalars(select(Invoice).where(Invoice.contract_id==contract.id).order_by(Invoice.id).with_for_update()).all()
    meter=db.execute(select(meter_handovers).where(meter_handovers.c.contract_id==contract.id).with_for_update()).mappings().first()
    data={'contract':{'id':contract.id,'start':contract.start_date.isoformat(),'end':contract.end_date.isoformat(),'rent':contract.monthly_rent,'cycle':contract.payment_cycle_months},
          'room_id':room.id,'period_start':start.isoformat(),'period_end':end.isoformat(),
          'property_prices':{'electricity':prop.electricity_unit_price,'water':prop.water_unit_price,'service':prop.service_unit_price},
          'property_input_version':db.scalar(select(input_revisions.c.version).where(input_revisions.c.property_id==prop.id).with_for_update()) or 0,
          'readings':[{'id':r.id,'type':r.utility_type,'period':r.period,'previous':r.previous_reading,'current':r.current_reading,
                       'version':db.scalar(select(reading_revision.c.version).where(reading_revision.c.reading_id==r.id).with_for_update()) or 0} for r in readings],
          'services':[item.model_dump(mode='json') for item in get_effective_services(db,contract)],
          'invoices':[{'id':i.id,'period':i.period,'total':i.total_amount} for i in invoices],
          'meter_handover':({**dict(meter),'handover_at':meter['handover_at'].isoformat(),'confirmed_at':meter['confirmed_at'].isoformat()} if meter else None)}
    payload=json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return payload,hashlib.sha256(payload.encode('utf-8')).hexdigest()

def create_final_approval(db,user,contract_id,data):
    require_trial(db)
    contract,room=locked_contract(db,user,contract_id)
    if contract.status not in {'active','pending_liquidation'}: raise HTTPException(409,'Hợp đồng không còn hợp lệ.')
    if data.period_start < contract.start_date or data.period_end > contract.end_date or data.period_end > date.today():
        raise HTTPException(422,'Khoảng tính không thuộc hợp đồng hoặc ở tương lai.')
    period=data.period_start.strftime('%Y-%m')
    if db.scalar(select(Invoice.id).where(Invoice.contract_id==contract_id,Invoice.period==period).with_for_update()):
        raise HTTPException(409,'Kỳ đã có hóa đơn; cần quy trình điều chỉnh được phê duyệt.')
    payload,digest=approval_inputs(db,contract,room,data.period_start,data.period_end)
    duplicate=db.execute(select(final_approvals.c.id).where(final_approvals.c.contract_id==contract_id,final_approvals.c.period==period,final_approvals.c.charge_type==data.charge_type,final_approvals.c.input_sha256==digest,final_approvals.c.status.in_(['pending','approved'])).with_for_update()).first()
    if duplicate: raise HTTPException(409,'Khoản này đã có yêu cầu đang chờ hoặc đã duyệt.')
    result=db.execute(insert(final_approvals).values(contract_id=contract_id,period=period,period_start=data.period_start,period_end=data.period_end,charge_type=data.charge_type,inputs=payload,input_sha256=digest,reason=data.reason,proposed_method=data.proposed_method,proposed_amount=data.proposed_amount,reference=data.reference,created_by=user.id,status='pending'))
    db.commit()
    return {'id':result.inserted_primary_key[0],'status':'pending','trial_only':True}

def list_final_approvals(db,user,contract_id):
    require_trial(db)
    contract,room=locked_contract(db,user,contract_id)
    rows=db.execute(select(final_approvals).where(final_approvals.c.contract_id==contract_id).order_by(final_approvals.c.id)).mappings().all()
    result=[]
    for row in rows:
        entry=dict(row)
        if entry['status'] in {'pending','approved'}:
            _,current=approval_inputs(db,contract,room,entry['period_start'],entry['period_end'])
            if current != entry['input_sha256']: entry['status']='stale'
        result.append(entry)
    return result

def decide_final_approval(db,user,contract_id,approval_id,data):
    require_trial(db)
    contract,room=locked_contract(db,user,contract_id)
    assert_can_manage(user,property_of_room(db,room))
    item=db.execute(select(final_approvals).where(final_approvals.c.id==approval_id,final_approvals.c.contract_id==contract_id).with_for_update()).mappings().first()
    if item is None: raise HTTPException(404,'Không tìm thấy yêu cầu.')
    if item['status']!='pending': raise HTTPException(409,'Yêu cầu đã được xử lý.')
    _,current=approval_inputs(db,contract,room,item['period_start'],item['period_end'])
    if current!=item['input_sha256']: raise HTTPException(409,'Dữ liệu đã thay đổi; cần yêu cầu mới.')
    db.execute(update(final_approvals).where(final_approvals.c.id==approval_id,final_approvals.c.status=='pending').values(status='approved' if data.approved else 'rejected',reviewed_by=user.id,reviewed_at=datetime.now(),decision_reason=data.reason))
    db.commit()
    return {'id':approval_id,'status':'approved' if data.approved else 'rejected','trial_only':True}

def issue_final_invoice(db,user,contract_id):
    from app.db.invoice_snapshot import invoice_snapshot
    from app.models.boarding import InvoiceMonth
    from app.services.service_assignment_service import get_effective_services
    require_trial(db)
    contract,room=locked_contract(db,user,contract_id)
    assert_can_manage(user,property_of_room(db,room))
    if contract.status not in {'active','pending_liquidation'}: raise HTTPException(409,'Hợp đồng không hợp lệ.')
    meter=db.execute(select(meter_handovers).where(meter_handovers.c.contract_id==contract.id).with_for_update()).mappings().first()
    if not meter or not final_meter_handover_is_verified(db,contract,{'handover_date':meter['handover_at'].date()}): raise HTTPException(409,'Chưa có chỉ số bàn giao hợp lệ.')
    end=meter['handover_at'].date();period=end.strftime('%Y-%m'); start=max(contract.start_date,end.replace(day=1))
    if db.scalar(select(Invoice.id).join(Contract).where(Contract.room_id==room.id,Invoice.period==period).with_for_update()):
        raise HTTPException(409,'Kỳ đã có hóa đơn; cần điều chỉnh được duyệt.')
    required={'rent','electricity','water'}
    for svc in get_effective_services(db,contract):
        code=svc.service_code.value
        if code not in {'electricity','water'}: required.add('service:'+code)
    rows=db.execute(select(final_approvals).where(final_approvals.c.contract_id==contract.id,final_approvals.c.period==period,final_approvals.c.status=='approved').order_by(final_approvals.c.id).with_for_update()).mappings().all()
    chosen={}
    for row in rows:
        if row['charge_type'] in required:
            if row['period_start']!=start or row['period_end']!=end: continue
            _,digest=approval_inputs(db,contract,room,start,end)
            if digest!=row['input_sha256']: continue
            if row['charge_type'] in chosen: raise HTTPException(409,'Có nhiều phê duyệt hợp lệ cho cùng khoản.')
            chosen[row['charge_type']]=row
    missing=required-set(chosen)
    if missing: raise HTTPException(409,'Thiếu phê duyệt: '+', '.join(sorted(missing)))
    if any(not (row['reference'] or '').strip() for row in chosen.values()): raise HTTPException(409,'Mỗi khoản phải có căn cứ hoặc tham chiếu thỏa thuận.')
    lines=[{'code':code,'amount':row['proposed_amount'],'quantity':None,'unit_price':None,'source':'manual_approval','approval_id':row['id'],'method':row['proposed_method'],'reference':row['reference'],'period_start':start.isoformat(),'period_end':end.isoformat()} for code,row in sorted(chosen.items())]
    rent=chosen['rent']['proposed_amount'];total=sum(line['amount'] for line in lines)
    if total>2147483647: raise HTTPException(422,'Tổng hóa đơn vượt giới hạn.')
    db.add(InvoiceMonth(room_id=room.id,period=period))
    invoice=Invoice(contract_id=contract.id,period=period,rent_amount=rent,utility_amount=total-rent,total_amount=total,status='unpaid')
    db.add(invoice);db.flush()
    readings={}
    for kind in ('electricity','water'):
        reading=db.get(UtilityReading,meter[f'{kind}_reading_id'])
        readings[kind]={'id':reading.id,'previous':reading.previous_reading,'current':reading.current_reading,'version':meter[f'{kind}_version']}
    document={'version':1,'billing_kind':'final_manual','invoice_id':invoice.id,'contract_id':contract.id,'room_id':room.id,'period':period,'period_start':start.isoformat(),'period_end':end.isoformat(),'contract_coverage_start':start.isoformat(),'contract_coverage_end':end.isoformat(),'rent_amount':rent,'utility_amount':total-rent,'lines':lines,'readings':readings,'missing_readings':[],'adjustments':[],'total_amount':total,'issued_at':invoice.created_at.isoformat(),'issued_by':user.id,'issued_status':'unpaid'}
    payload=json.dumps(document,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    db.execute(insert(invoice_snapshot).values(invoice_id=invoice.id,payload=payload,sha256=hashlib.sha256(payload.encode('utf-8')).hexdigest()))
    for row in chosen.values():
        db.execute(update(final_approvals).where(final_approvals.c.id==row['id'],final_approvals.c.status=='approved').values(status='invoiced',invoice_id=invoice.id))
    save(db,invoice)
    return {'invoice_id':invoice.id,'total_amount':total,'trial_only':True}

def totals(db, contract_id):
    invoices=db.scalars(select(Invoice).where(Invoice.contract_id==contract_id).order_by(Invoice.id).with_for_update()).all()
    debts=[]
    for inv in invoices:
        payments=db.scalars(select(Payment).where(Payment.invoice_id==inv.id).with_for_update()).all()
        paid=sum(p.amount for p in payments)
        debts.append({'id':inv.id,'period':inv.period,'total':inv.total_amount,'paid':paid,'balance':inv.total_amount-paid})
    return debts

def final_period_gaps(db, contract, actual_end_date, debts):
    """Minimum evidence only; existing invoice has no immutable item snapshot."""
    expected=[]
    cursor=contract.start_date.replace(day=1)
    last=actual_end_date.replace(day=1)
    while cursor <= last:
        expected.append(cursor.strftime('%Y-%m'))
        cursor=date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    periods={row['period'] for row in debts}
    missing=[f'Thiếu hóa đơn kỳ {period}' for period in expected if period not in periods]
    last_period=actual_end_date.strftime('%Y-%m')
    kinds=set(db.scalars(select(UtilityReading.utility_type).where(UtilityReading.room_id==contract.room_id,UtilityReading.period==last_period).with_for_update()))
    missing.extend(f'Thiếu chỉ số {kind} kỳ {last_period}' for kind in ('electricity','water') if kind not in kinds)
    return missing

def final_invoice_evidence_is_complete(db, contract, settlement):
    from app.db.invoice_snapshot import invoice_snapshot
    end=settlement['handover_date']
    invoices=db.scalars(select(Invoice).where(Invoice.contract_id==contract.id).with_for_update()).all()
    for invoice in invoices:
        row=db.execute(select(invoice_snapshot).where(invoice_snapshot.c.invoice_id==invoice.id)).mappings().first()
        if not row or hashlib.sha256(row['payload'].encode('utf-8')).hexdigest()!=row['sha256']: return False
        review=db.execute(select(invoice_reviews).where(invoice_reviews.c.invoice_id==invoice.id,invoice_reviews.c.contract_id==contract.id)).mappings().first()
        if not review or review['snapshot_sha256'] != row['sha256']: return False
        try:
            doc=json.loads(row['payload'])
            if (doc['invoice_id']!=invoice.id or doc['contract_id']!=contract.id or doc['room_id']!=contract.room_id
                or doc['period']!=invoice.period or doc['total_amount']!=invoice.total_amount
                or sum(line['amount'] for line in doc['lines'])!=invoice.total_amount or doc['missing_readings']): return False
            if invoice.period==end.strftime('%Y-%m'):
                if doc.get('billing_kind')!='final_manual' or doc['period_end']!=end.isoformat(): return False
                for line in doc['lines']:
                    approval=db.execute(select(final_approvals).where(final_approvals.c.id==line.get('approval_id'),final_approvals.c.invoice_id==invoice.id,final_approvals.c.status=='invoiced')).mappings().first()
                    if not approval or approval['proposed_amount']!=line['amount']: return False
            elif doc['contract_coverage_start']!=doc['period_start'] or doc['contract_coverage_end']!=doc['period_end']: return False
        except (KeyError, TypeError, ValueError): return False
    return bool(invoices)

def final_meter_handover_is_verified(db, contract, settlement):
    from app.db.reading_revision import reading_revision
    row=db.execute(select(meter_handovers).where(meter_handovers.c.contract_id==contract.id).with_for_update()).mappings().first()
    if not row or row['handover_at'].date()!=settlement['handover_date']: return False
    for kind in ('electricity','water'):
        reading=db.get(UtilityReading,row[f'{kind}_reading_id'])
        version=db.scalar(select(reading_revision.c.version).where(reading_revision.c.reading_id==row[f'{kind}_reading_id']).with_for_update()) or 0
        if not reading or reading.room_id!=contract.room_id or reading.utility_type!=kind or reading.period!=row['handover_at'].strftime('%Y-%m') or version!=row[f'{kind}_version']: return False
    return True

def confirm_meter_handover(db,user,contract_id,data):
    from app.db.reading_revision import reading_revision
    require_trial(db)
    contract,room=locked_contract(db,user,contract_id)
    at=data.handover_at
    if at.tzinfo is not None or at>datetime.now() or not contract.start_date<=at.date()<=contract.end_date:
        raise HTTPException(422,'Thời điểm bàn giao không hợp lệ.')
    if db.execute(select(meter_handovers.c.contract_id).where(meter_handovers.c.contract_id==contract.id).with_for_update()).first(): raise HTTPException(409,'Đã xác nhận chỉ số bàn giao.')
    period=at.strftime('%Y-%m')
    if db.scalar(select(Invoice.id).where(Invoice.contract_id==contract.id,Invoice.period==period).with_for_update()): raise HTTPException(409,'Kỳ đã lập hóa đơn; cần quy trình điều chỉnh.')
    values={}
    for kind in ('electricity','water'):
        rid=getattr(data,f'{kind}_reading_id')
        reading=db.scalar(select(UtilityReading).where(UtilityReading.id==rid,UtilityReading.room_id==room.id,UtilityReading.utility_type==kind,UtilityReading.period==period).with_for_update())
        if not reading: raise HTTPException(404,f'Không tìm thấy chỉ số {kind} của phòng và kỳ.')
        previous=db.scalar(select(UtilityReading).where(UtilityReading.room_id==room.id,UtilityReading.utility_type==kind,UtilityReading.period<period).order_by(UtilityReading.period.desc()).limit(1).with_for_update())
        previous_month=(at.date().replace(day=1)-timedelta(days=1)).strftime('%Y-%m')
        if previous and previous.period!=previous_month and contract.start_date.strftime('%Y-%m')<period: raise HTTPException(409,f'Thiếu kỳ chỉ số {kind}; cần đối soát.')
        if previous and previous.current_reading != reading.previous_reading: raise HTTPException(409,f'Chỉ số {kind} không nối tiếp kỳ trước; cần kiểm tra công tơ.')
        if not previous and contract.start_date.replace(day=1)<at.date().replace(day=1): raise HTTPException(409,f'Thiếu chỉ số {kind} kỳ trước; cần đối soát.')
        values[f'{kind}_reading_id']=rid
        values[f'{kind}_version']=db.scalar(select(reading_revision.c.version).where(reading_revision.c.reading_id==rid).with_for_update()) or 0
        if values[f'{kind}_version'] != getattr(data,f'{kind}_expected_version'): raise HTTPException(409,f'Chỉ số {kind} đã thay đổi; cần tải lại trước khi xác nhận.')
    db.execute(insert(meter_handovers).values(contract_id=contract.id,handover_at=at,recorded_by=user.id,confirmed_by=user.id,**values))
    db.commit()
    return {'contract_id':contract.id,'confirmed':True,'trial_only':True}

def review_invoice(db,user,contract_id,invoice_id):
    require_trial(db)
    contract,_=locked_contract(db,user,contract_id)
    invoice=db.scalar(select(Invoice).where(Invoice.id==invoice_id,Invoice.contract_id==contract.id).with_for_update())
    if invoice is None: raise HTTPException(404,'Không tìm thấy hóa đơn của hợp đồng.')
    from app.services.billing_service import read_invoice_snapshot
    from app.db.invoice_snapshot import invoice_snapshot
    evidence=read_invoice_snapshot(db,user,invoice_id)
    if evidence['status']!='complete': raise HTTPException(409,'Chứng từ thiếu hoặc không toàn vẹn; cần đối soát thủ công.')
    old=db.execute(select(invoice_reviews).where(invoice_reviews.c.invoice_id==invoice_id).with_for_update()).first()
    if old: raise HTTPException(409,'Hóa đơn đã được xác nhận đối soát.')
    checksum=db.scalar(select(invoice_snapshot.c.sha256).where(invoice_snapshot.c.invoice_id==invoice_id))
    db.execute(insert(invoice_reviews).values(invoice_id=invoice_id,contract_id=contract_id,snapshot_sha256=checksum,reviewed_by=user.id))
    db.commit()
    return {'invoice_id':invoice_id,'reviewed':True}

def snapshot(db, contract_id):
    require_trial(db)
    settlement=db.execute(select(settlements).where(settlements.c.contract_id==contract_id)).mappings().first()
    items=db.execute(select(damages).where(damages.c.contract_id==contract_id).order_by(damages.c.id)).mappings().all()
    receivable=db.execute(select(receivables).where(receivables.c.contract_id==contract_id)).mappings().first()
    reviews=db.execute(select(invoice_reviews).where(invoice_reviews.c.contract_id==contract_id)).mappings().all()
    meter=db.execute(select(meter_handovers).where(meter_handovers.c.contract_id==contract_id)).mappings().first()
    return {'settlement':dict(settlement) if settlement else None,'damages':[dict(x) for x in items], 'receivable':dict(receivable) if receivable else None, 'invoice_reviews':[dict(x) for x in reviews], 'meter_handover':dict(meter) if meter else None}

def update_damage_receivable(db, contract, user):
    items=db.execute(select(damages).where(damages.c.contract_id==contract.id).with_for_update()).mappings().all()
    shortfall=max(0,sum(item['amount'] for item in items if item['confirmed_by'] is not None)-contract.deposit)
    existing=db.execute(select(receivables).where(receivables.c.contract_id==contract.id).with_for_update()).mappings().first()
    if shortfall and existing is None:
        db.execute(insert(receivables).values(contract_id=contract.id,amount=shortfall,status='unpaid',created_by=user.id))
    elif shortfall and existing:
        if existing['status'] != 'unpaid': raise HTTPException(409,'Khoản phải thu đã xử lý; không thể tự thay đổi.')
        db.execute(update(receivables).where(receivables.c.contract_id==contract.id).values(amount=shortfall))

def add_damage(db,user,contract_id,data):
    require_trial(db)
    contract,room=locked_contract(db,user,contract_id)
    if contract.status not in {'active','pending_liquidation'}: raise HTTPException(409,'Hợp đồng đã kết thúc.')
    existing=db.execute(select(settlements).where(settlements.c.contract_id==contract_id).with_for_update()).mappings().first()
    if existing and existing['refund_amount'] is not None: raise HTTPException(409,'Cọc đã được quyết toán.')
    result=db.execute(insert(damages).values(contract_id=contract_id,description=data.description.strip(),amount=data.amount,created_by=user.id,confirmed_by=user.id if data.confirmed else None,confirmed_at=datetime.now() if data.confirmed else None))
    if data.confirmed: update_damage_receivable(db,contract,user)
    db.commit()
    return {'id':result.inserted_primary_key[0]}

def handover(db,user,contract_id,data):
    require_trial(db)
    contract,room=locked_contract(db,user,contract_id)
    if contract.status not in {'active','pending_liquidation'}: raise HTTPException(409,'Hợp đồng không thể bàn giao.')
    if db.execute(select(settlements.c.contract_id).where(settlements.c.contract_id==contract_id).with_for_update()).first(): raise HTTPException(409,'Hợp đồng đã bàn giao.')
    if not data.confirmed or not contract.start_date <= data.actual_end_date <= date.today(): raise HTTPException(422,'Ngày bàn giao hoặc xác nhận không hợp lệ.')
    debts=totals(db,contract_id)
    gaps=final_period_gaps(db,contract,data.actual_end_date,debts)
    if gaps: raise HTTPException(409,'; '.join(gaps))
    db.execute(insert(settlements).values(contract_id=contract_id,handover_date=data.actual_end_date,reason=data.reason.strip(),created_by=user.id,damage_shortfall=0))
    contract.status='pending_liquidation'
    if room.status!='maintenance': room.status='available'
    save(db,contract,room)
    return {'contract_id':contract_id,'handover_recorded':True,'outstanding':sum(row['balance'] for row in debts),'room_status':room.status}

def confirm_damage(db,user,contract_id,damage_id):
    require_trial(db)
    contract,_=locked_contract(db,user,contract_id)
    settlement=db.execute(select(settlements).where(settlements.c.contract_id==contract_id).with_for_update()).mappings().first()
    if settlement and settlement['refund_amount'] is not None: raise HTTPException(409,'Cọc đã được quyết toán.')
    item=db.execute(select(damages).where(damages.c.contract_id==contract_id,damages.c.id==damage_id).with_for_update()).mappings().first()
    if not item: raise HTTPException(404,'Không tìm thấy hư hỏng.')
    if item['confirmed_by'] is not None: raise HTTPException(409,'Hư hỏng đã được xác nhận.')
    db.execute(update(damages).where(damages.c.id==damage_id).values(confirmed_by=user.id,confirmed_at=datetime.now()))
    update_damage_receivable(db,contract,user)
    db.commit()
    return {'id':damage_id,'confirmed':True}

def record_refund(db,user,contract_id,data):
    require_trial(db)
    contract,room=locked_contract(db,user,contract_id)
    settlement=db.execute(select(settlements).where(settlements.c.contract_id==contract_id).with_for_update()).mappings().first()
    if not data.confirmed: raise HTTPException(422,'Cần xác nhận.')
    if not settlement: raise HTTPException(409,'Chưa ghi nhận bàn giao.')
    if settlement['refund_amount'] is not None: raise HTTPException(409,'Cọc đã được ghi nhận quyết toán.')
    if contract.deposit > 0 and contract.deposit_status != 'held': raise HTTPException(409,'Tiền cọc chưa được ghi nhận đang giữ hoặc đã quyết toán.')
    debts=totals(db,contract_id)
    gaps=final_period_gaps(db,contract,settlement['handover_date'],debts)
    if gaps: raise HTTPException(409,'; '.join(gaps))
    if any(row['balance']>0 for row in debts): raise HTTPException(409,'Công nợ phải được thanh toán riêng và đầy đủ trước khi hoàn cọc.')
    # US-22 currently stores only aggregate invoice amounts, with no immutable
    # breakdown of final readings, prices and services. A monthly invoice and
    # meter rows alone cannot prove the final amount; fail closed until that
    # evidence and its review workflow exist.
    if not final_invoice_evidence_is_complete(db,contract,settlement):
        raise HTTPException(409,'Chưa thể quyết toán: thiếu chứng từ chi tiết bất biến cho hóa đơn cuối kỳ và xác nhận đối soát.')
    if not final_meter_handover_is_verified(db,contract,settlement):
        raise HTTPException(409,'Chưa có chỉ số bàn giao được xác nhận; không thể hoàn cọc.')
    items=db.execute(select(damages).where(damages.c.contract_id==contract_id).with_for_update()).mappings().all()
    if any(item['confirmed_by'] is None for item in items): raise HTTPException(409,'Còn hư hỏng chưa được xác nhận.')
    receivable=db.execute(select(receivables).where(receivables.c.contract_id==contract_id).with_for_update()).mappings().first()
    if receivable and receivable['status']!='paid': raise HTTPException(409,'Khoản bồi thường vượt cọc chưa được xử lý.')
    damage_total=sum(item['amount'] for item in items if item['confirmed_by'] is not None)
    refund=max(0,contract.deposit-damage_total);shortfall=max(0,damage_total-contract.deposit)
    if refund and not data.method: raise HTTPException(422,'Cần phương thức hoàn cọc.')
    if refund and data.method=='bank_transfer' and not (data.reference or '').strip(): raise HTTPException(422,'Cần mã tham chiếu chuyển khoản.')
    db.execute(update(settlements).where(settlements.c.contract_id==contract_id).values(refund_amount=refund,damage_shortfall=shortfall,refunded_by=user.id,refunded_at=datetime.now(),refund_method=data.method,refund_reference=(data.reference or '').strip() or None))
    contract.deposit_status='returned' if refund else 'deducted'
    contract.deposit_returned_amount=refund
    contract.status='expired'
    save(db,contract)
    return {'refund_amount':refund,'damage_shortfall':shortfall,'recorded':True,'trial_only':True}
