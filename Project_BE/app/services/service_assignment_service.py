from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, PropertyServicePrice, Room
from app.models.service_assignment import ServiceAssignment
from app.models.user import User
from app.schemas.service_assignment import (
    EffectiveServiceResponse,
    ServiceAssignmentResponse,
    ServiceAssignmentUpdate,
    ServiceAssignmentWrite,
)
from app.schemas.service_price import BillingUnit, ServiceCode
from app.services import service_price_service
from app.services.access_scope import (
    assert_can_operate,
    get_contract,
    get_room,
    property_of_room,
)
from app.services.db_util import save


def _service_catalog_entry(code: ServiceCode) -> tuple[str, tuple[BillingUnit, ...]]:
    return service_price_service.CATALOG[code]


def _get_target_property(
    db: Session, data: ServiceAssignmentWrite
) -> tuple[PropertyServicePrice | None, int | None, int | None]:
    if data.room_id is not None:
        room = get_room(db, data.room_id)
        return (
            _property_service_price(
                db, property_of_room(db, room).id, data.service_code
            ),
            room.property_id,
            data.room_id,
        )
    contract = get_contract(db, data.contract_id)
    room = get_room(db, contract.room_id)
    return (
        _property_service_price(db, property_of_room(db, room).id, data.service_code),
        room.property_id,
        contract.id,
    )


def _property_service_price(
    db: Session, property_id: int, service_code: ServiceCode
) -> PropertyServicePrice | None:
    return db.get(PropertyServicePrice, (property_id, service_code.value))


def _validate_quantity(quantity: int) -> None:
    if quantity < 1:
        raise HTTPException(
            status_code=422, detail="Số lượng phải lớn hơn hoặc bằng 1."
        )


def _contract_accepts_services(contract: Contract) -> bool:
    return (
        contract.status in {"created", "active"} and contract.end_date >= date.today()
    )


def _serialize_response(
    db: Session, assignment: ServiceAssignment
) -> ServiceAssignmentResponse:
    code = ServiceCode(assignment.service_code)
    service_name, _ = _service_catalog_entry(code)
    property_id = None
    if assignment.room_id is not None:
        room = get_room(db, assignment.room_id)
        property_id = property_of_room(db, room).id
    elif assignment.contract_id is not None:
        contract = get_contract(db, assignment.contract_id)
        room = get_room(db, contract.room_id)
        property_id = property_of_room(db, room).id
    price = (
        db.get(PropertyServicePrice, (property_id, code.value))
        if property_id is not None
        else None
    )
    billing_unit = BillingUnit(price.billing_unit) if price else None
    unit_price = price.unit_price if price else None
    effective_price = (
        assignment.price_override
        if assignment.price_override is not None
        else price.unit_price if price else None
    )
    return ServiceAssignmentResponse(
        id=assignment.id,
        service_code=code,
        service_name=service_name,
        billing_unit=billing_unit,
        unit_price=unit_price,
        price_override=assignment.price_override,
        effective_price=effective_price,
        quantity=assignment.quantity,
        room_id=assignment.room_id,
        contract_id=assignment.contract_id,
        assigned_by=assignment.assigned_by,
        created_at=assignment.created_at,
    )


def _serialize_effective_service(
    db: Session,
    contract: Contract,
    service_code: str,
    source: str,
    assignment: ServiceAssignment,
) -> EffectiveServiceResponse:
    code = ServiceCode(service_code)
    service_name, _ = _service_catalog_entry(code)
    room = get_room(db, contract.room_id)
    property_id = property_of_room(db, room).id
    price = db.get(PropertyServicePrice, (property_id, service_code))
    effective_price = (
        assignment.price_override
        if assignment.price_override is not None
        else price.unit_price if price else None
    )
    return EffectiveServiceResponse(
        service_code=code,
        service_name=service_name,
        billing_unit=BillingUnit(price.billing_unit) if price else None,
        unit_price=price.unit_price if price else None,
        price_override=assignment.price_override,
        effective_price=effective_price,
        quantity=assignment.quantity,
        source=source,
        assignment_id=assignment.id,
        room_id=assignment.room_id,
        contract_id=assignment.contract_id,
    )


def _assert_target_valid(
    db: Session, user: User, room_id: int | None, contract_id: int | None
) -> tuple[Room | None, Contract | None]:
    if room_id is not None:
        room = get_room(db, room_id)
        assert_can_operate(db, user, property_of_room(db, room))
        return room, None
    contract = get_contract(db, contract_id)
    room = get_room(db, contract.room_id)
    assert_can_operate(db, user, property_of_room(db, room))
    if not _contract_accepts_services(contract):
        raise HTTPException(
            status_code=409, detail="Chỉ gán dịch vụ cho hợp đồng chưa kết thúc."
        )
    return room, contract


def create_service_assignment(
    db: Session, user: User, data: ServiceAssignmentWrite
) -> ServiceAssignmentResponse:
    if data.room_id is None and data.contract_id is None:
        raise HTTPException(
            status_code=422, detail="Phải chọn đúng một trong room_id hoặc contract_id."
        )
    if data.room_id is not None and data.contract_id is not None:
        raise HTTPException(
            status_code=422, detail="Phải chọn đúng một trong room_id hoặc contract_id."
        )

    room = None
    contract = None
    if data.room_id is not None:
        room = get_room(db, data.room_id)
        property_obj = property_of_room(db, room)
        assert_can_operate(db, user, property_obj)
        contract = None
    else:
        contract = get_contract(db, data.contract_id)
        room = get_room(db, contract.room_id)
        property_obj = property_of_room(db, room)
        assert_can_operate(db, user, property_obj)
        if not _contract_accepts_services(contract):
            raise HTTPException(
                status_code=409, detail="Chỉ gán dịch vụ cho hợp đồng chưa kết thúc."
            )

    if data.price_override is not None and data.price_override < 0:
        raise HTTPException(status_code=422, detail="Giá riêng không được nhỏ hơn 0.")

    _validate_quantity(data.quantity)
    target_filter = (
        (
            ServiceAssignment.room_id == data.room_id,
            ServiceAssignment.service_code == data.service_code.value,
        )
        if data.room_id is not None
        else (
            ServiceAssignment.contract_id == data.contract_id,
            ServiceAssignment.service_code == data.service_code.value,
        )
    )
    existing = db.scalar(select(ServiceAssignment.id).where(*target_filter))
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Dịch vụ này đã được gán cho phòng/hợp đồng này."
        )

    assignment = ServiceAssignment(
        service_code=data.service_code.value,
        room_id=data.room_id,
        contract_id=data.contract_id,
        quantity=data.quantity,
        price_override=data.price_override,
        assigned_by=user.id,
    )
    db.add(assignment)
    save(db, assignment)
    return _serialize_response(db, assignment)


def list_service_assignments(
    db: Session, user: User, room_id: int | None = None, contract_id: int | None = None
) -> list[ServiceAssignmentResponse]:
    if room_id is None and contract_id is None:
        raise HTTPException(
            status_code=422, detail="Phải truyền room_id hoặc contract_id."
        )
    if room_id is not None and contract_id is not None:
        raise HTTPException(
            status_code=422, detail="Chỉ một trong room_id hoặc contract_id được phép."
        )

    if room_id is not None:
        room = get_room(db, room_id)
        assert_can_operate(db, user, property_of_room(db, room))
        rows = (
            db.execute(
                select(ServiceAssignment)
                .where(ServiceAssignment.room_id == room_id)
                .order_by(ServiceAssignment.id)
            )
            .scalars()
            .all()
        )
    else:
        contract = get_contract(db, contract_id)
        room = get_room(db, contract.room_id)
        assert_can_operate(db, user, property_of_room(db, room))
        rows = (
            db.execute(
                select(ServiceAssignment)
                .where(ServiceAssignment.contract_id == contract_id)
                .order_by(ServiceAssignment.id)
            )
            .scalars()
            .all()
        )

    return [_serialize_response(db, assignment) for assignment in rows]


def update_service_assignment(
    db: Session, user: User, assignment_id: int, data: ServiceAssignmentUpdate
) -> ServiceAssignmentResponse:
    assignment = db.get(ServiceAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy gán dịch vụ.")
    if assignment.contract_id is not None:
        contract = get_contract(db, assignment.contract_id)
        room = get_room(db, contract.room_id)
        assert_can_operate(db, user, property_of_room(db, room))
        if not _contract_accepts_services(contract):
            raise HTTPException(
                status_code=409,
                detail="Không thể sửa gán dịch vụ cho hợp đồng đã kết thúc.",
            )
    else:
        room = get_room(db, assignment.room_id)
        assert_can_operate(db, user, property_of_room(db, room))

    if data.price_override is not None and data.price_override < 0:
        raise HTTPException(status_code=422, detail="Giá riêng không được nhỏ hơn 0.")

    if (
        data.service_code is not None
        and data.service_code.value != assignment.service_code
    ):
        target_filter = (
            (ServiceAssignment.room_id == assignment.room_id)
            if assignment.room_id is not None
            else (ServiceAssignment.contract_id == assignment.contract_id)
        )
        duplicate = db.scalar(
            select(ServiceAssignment.id).where(
                target_filter,
                ServiceAssignment.service_code == data.service_code.value,
                ServiceAssignment.id != assignment.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail="Dịch vụ này đã được gán cho phòng/hợp đồng này.",
            )
        assignment.service_code = data.service_code.value

    if data.quantity is not None:
        _validate_quantity(data.quantity)
        assignment.quantity = data.quantity
    if "price_override" in data.model_fields_set:
        assignment.price_override = data.price_override
    save(db, assignment)
    return _serialize_response(db, assignment)


def delete_service_assignment(db: Session, user: User, assignment_id: int) -> None:
    assignment = db.get(ServiceAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy gán dịch vụ.")
    if assignment.contract_id is not None:
        contract = get_contract(db, assignment.contract_id)
        room = get_room(db, contract.room_id)
        assert_can_operate(db, user, property_of_room(db, room))
        if not _contract_accepts_services(contract):
            raise HTTPException(
                status_code=409,
                detail="Không thể gỡ gán dịch vụ cho hợp đồng đã kết thúc.",
            )
    else:
        room = get_room(db, assignment.room_id)
        assert_can_operate(db, user, property_of_room(db, room))
    db.delete(assignment)
    save(db)


def get_effective_services(
    db: Session, contract: Contract
) -> list[EffectiveServiceResponse]:
    room_id = contract.room_id
    room_assignments = (
        db.execute(
            select(ServiceAssignment)
            .where(ServiceAssignment.room_id == room_id)
            .order_by(ServiceAssignment.id)
        )
        .scalars()
        .all()
    )
    contract_assignments = (
        db.execute(
            select(ServiceAssignment)
            .where(ServiceAssignment.contract_id == contract.id)
            .order_by(ServiceAssignment.id)
        )
        .scalars()
        .all()
    )

    effective_by_code: dict[str, tuple[str, ServiceAssignment]] = {}
    for assignment in contract_assignments:
        effective_by_code[assignment.service_code] = ("contract", assignment)
    for assignment in room_assignments:
        effective_by_code.setdefault(assignment.service_code, ("room", assignment))

    ordered_codes = [code.value for code in service_price_service.CATALOG]
    responses: list[EffectiveServiceResponse] = []
    for service_code in ordered_codes:
        if service_code not in effective_by_code:
            continue
        source, assignment = effective_by_code[service_code]
        responses.append(
            _serialize_effective_service(db, contract, service_code, source, assignment)
        )
    return responses


def get_contract_service_list(
    db: Session, user: User, contract_id: int
) -> list[EffectiveServiceResponse]:
    contract = get_contract(db, contract_id)
    room = get_room(db, contract.room_id)
    assert_can_operate(db, user, property_of_room(db, room))
    return get_effective_services(db, contract)
