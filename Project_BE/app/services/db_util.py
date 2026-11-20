from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session


def execute_write(db: Session, operation, *args):
    """Rollback safely on lock errors without retrying a transaction implicitly."""
    try:
        return operation(db, *args)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Giao dịch không thể hoàn tất; vui lòng thử lại.") from exc


def save(db: Session, *objects) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dữ liệu bị trùng hoặc vi phạm ràng buộc.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể truy cập database. Vui lòng thử lại sau.") from exc
    for obj in objects:
        db.refresh(obj)
