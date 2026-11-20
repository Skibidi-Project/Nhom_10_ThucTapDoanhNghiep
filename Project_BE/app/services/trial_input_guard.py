"""Serialize/version price and assignment writers for the isolated US-16 trial."""
from sqlalchemy import insert, select, update
from app.models.boarding import Property, Room

def touch_property_inputs(db, property_id, room_id=None):
    from app.services.settlement_trial import allowed
    if not allowed(db):
        return
    from app.db.settlement_trial import input_revisions
    if room_id is not None:
        db.scalar(select(Room.id).where(Room.id==room_id).with_for_update())
    db.scalar(select(Property.id).where(Property.id==property_id).with_for_update())
    version=db.scalar(select(input_revisions.c.version).where(input_revisions.c.property_id==property_id).with_for_update())
    if version is None:
        db.execute(insert(input_revisions).values(property_id=property_id,version=1))
    else:
        db.execute(update(input_revisions).where(input_revisions.c.property_id==property_id).values(version=version+1))
