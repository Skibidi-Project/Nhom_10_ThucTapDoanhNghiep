from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.boarding import Property
from app.models.building import Building, Floor
from app.models.user import User
from app.schemas.building import (
    BuildingCreate,
    BuildingResponse,
    BuildingUpdate,
    FloorRename,
    FloorResponse,
    check_floor_names,
)
from app.services.access_scope import assert_can_operate, get_property
from app.services.db_util import save


def _get_building(db: Session, user: User, building_id: int) -> Building:
    building = db.scalar(
        select(Building).options(selectinload(Building.floors)).where(Building.id == building_id)
    )
    if building is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tòa nhà.")
    property_obj = get_property(db, building.property_id)
    assert_can_operate(db, user, property_obj)
    return building


def _response(building: Building) -> BuildingResponse:
    floors = sorted(building.floors, key=lambda item: item.number)
    return BuildingResponse(
        id=building.id,
        property_id=building.property_id,
        name=building.name,
        floor_count=len(floors),
        floors=[FloorResponse.model_validate(floor) for floor in floors],
    )


def _name_taken(db: Session, property_id: int, name: str, ignore_id: int | None = None) -> bool:
    stmt = select(Building.id).where(
        Building.property_id == property_id,
        func.lower(Building.name) == name.lower(),
    )
    if ignore_id is not None:
        stmt = stmt.where(Building.id != ignore_id)
    return db.scalar(stmt) is not None


def list_buildings(db: Session, user: User, property_id: int) -> list[BuildingResponse]:
    property_obj: Property = get_property(db, property_id)
    assert_can_operate(db, user, property_obj)
    buildings = db.scalars(
        select(Building)
        .options(selectinload(Building.floors))
        .where(Building.property_id == property_id)
        .order_by(Building.id)
    ).all()
    return [_response(building) for building in buildings]


def read_building(db: Session, user: User, building_id: int) -> BuildingResponse:
    return _response(_get_building(db, user, building_id))


def create_building(db: Session, user: User, property_id: int, data: BuildingCreate) -> BuildingResponse:
    property_obj = get_property(db, property_id)
    assert_can_operate(db, user, property_obj)
    if _name_taken(db, property_id, data.name):
        raise HTTPException(status_code=409, detail="Tên tòa nhà đã tồn tại trong khu trọ.")
    names = data.floor_names or [f"Tầng {number}" for number in range(1, data.floor_count + 1)]
    building = Building(
        property_id=property_id,
        name=data.name,
        floors=[Floor(number=number, name=name) for number, name in enumerate(names, start=1)],
    )
    db.add(building)
    save(db, building)
    return _response(building)


def update_building(db: Session, user: User, building_id: int, data: BuildingUpdate) -> BuildingResponse:
    building = _get_building(db, user, building_id)
    if data.name is not None:
        if _name_taken(db, building.property_id, data.name, ignore_id=building.id):
            raise HTTPException(status_code=409, detail="Tên tòa nhà đã tồn tại trong khu trọ.")
        building.name = data.name

    if data.floor_count is not None or data.floor_names is not None:
        existing = sorted(building.floors, key=lambda floor: floor.number)
        count = data.floor_count if data.floor_count is not None else len(data.floor_names)
        if count < len(existing):
            for floor in existing[count:]:
                building.floors.remove(floor)
        elif count > len(existing):
            for number in range(len(existing) + 1, count + 1):
                building.floors.append(Floor(number=number, name=f"Tầng {number}"))

        if data.floor_names is not None:
            for floor, name in zip(sorted(building.floors, key=lambda f: f.number), data.floor_names):
                floor.name = name
        try:
            check_floor_names([floor.name for floor in building.floors])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    save(db, building)
    return _response(building)


def rename_floor(db: Session, user: User, building_id: int, floor_id: int, data: FloorRename) -> FloorResponse:
    building = _get_building(db, user, building_id)
    floor = next((item for item in building.floors if item.id == floor_id), None)
    if floor is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tầng thuộc tòa nhà này.")
    if any(item.id != floor.id and item.name.casefold() == data.name.casefold() for item in building.floors):
        raise HTTPException(status_code=409, detail="Tên tầng đã tồn tại trong tòa nhà.")
    floor.name = data.name
    save(db, floor)
    return FloorResponse.model_validate(floor)


def delete_building(db: Session, user: User, building_id: int) -> None:
    building = _get_building(db, user, building_id)
    db.delete(building)
    save(db)
