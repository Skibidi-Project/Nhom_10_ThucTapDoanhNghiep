from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.rbac import Role
from app.models.user import User
from app.schemas.user import ProfileUpdate, UserCreate, UserLogin
from app.services.db_util import save

password_hasher = PasswordHasher()


def register_user(db: Session, data: UserCreate) -> User:
    try:
        existing = db.scalar(select(User).where(or_(User.email == str(data.email), User.phone == data.phone)))
        if existing:
            raise HTTPException(status_code=409, detail="Email hoặc số điện thoại đã được sử dụng.")
        user = User(
            full_name=data.full_name, email=str(data.email), phone=data.phone,
            password_hash=password_hasher.hash(data.password), role=Role.TENANT.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
        # Ràng buộc UNIQUE vẫn bảo vệ khi hai request đăng ký đồng thời.
        db.rollback()
        code = exc.orig.args[0] if exc.orig.args else None
        if code == 1062:
            raise HTTPException(status_code=409, detail="Email hoặc số điện thoại đã được sử dụng.") from exc
        raise HTTPException(status_code=503, detail="Không thể lưu tài khoản vào database.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể truy cập database. Vui lòng thử lại sau.") from exc


def login_user(db: Session, data: UserLogin) -> User:
    try:
        column = User.email if "@" in data.identifier else User.phone
        user = db.scalar(select(User).where(column == data.identifier))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể truy cập database. Vui lòng thử lại sau.") from exc
    if user:
        try:
            password_hasher.verify(user.password_hash, data.password)
            return user
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            pass
    raise HTTPException(status_code=401, detail="Email/SĐT hoặc mật khẩu không đúng.")


def list_users(db: Session) -> list[User]:
    try:
        return list(db.scalars(select(User).order_by(User.id)))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể truy cập database. Vui lòng thử lại sau.") from exc


def get_account(db: Session, actor: User, user_id: int) -> User:
    if actor.role != Role.ADMIN.value and actor.id != user_id:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem tài khoản này.")
    target = db.get(User, user_id)
    if target is None:
        if actor.role != Role.ADMIN.value:
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem tài khoản này.")
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    return target


def update_profile(db: Session, user: User, data: ProfileUpdate) -> User:
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.phone is not None and data.phone != user.phone:
        taken = db.scalar(select(User).where(User.phone == data.phone))
        if taken is not None:
            raise HTTPException(status_code=409, detail="Số điện thoại đã được sử dụng.")
        user.phone = data.phone
    save(db, user)
    return user


def assign_role(db: Session, user_id: int, role: str) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    target.role = role
    save(db, target)
    return target
