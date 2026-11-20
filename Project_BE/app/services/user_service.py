from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.rbac import Role
from app.models.boarding import Property, PropertyManager, TenantProfile
from app.models.user import User
from app.schemas.user import ProfileUpdate, UserCreate, UserLogin
from app.services.db_util import save

password_hasher = PasswordHasher()


def register_user(db: Session, data: UserCreate) -> User:
    try:
        duplicate = User.email == str(data.email)
        if data.phone is not None:
            duplicate = or_(duplicate, User.phone == data.phone)
        if db.scalar(select(User.id).where(duplicate)) is not None:
            raise HTTPException(status_code=409, detail="Email hoặc số điện thoại đã được sử dụng.")
        user = User(
            full_name=data.full_name,
            email=str(data.email),
            phone=data.phone,
            password_hash=password_hasher.hash(data.password),
            role=Role.TENANT.value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError as exc:
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


def list_users(
    db: Session,
    *,
    q: str | None = None,
    role: str | None = None,
    page: int = 1,
    page_size: int = 10,
):
    try:
        stmt = select(User)
        if q and q.strip():
            term = q.strip()
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            stmt = stmt.where(
                or_(
                    func.lower(User.full_name).like(func.lower(pattern), escape="\\"),
                    func.lower(User.email).like(func.lower(pattern), escape="\\"),
                    func.lower(User.phone).like(func.lower(pattern), escape="\\"),
                )
            )
        if role:
            stmt = stmt.where(User.role == role)

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = db.scalar(count_stmt) or 0
        items = db.scalars(stmt.order_by(User.id).limit(page_size).offset((page - 1) * page_size)).all()
        return {"items": items, "total": total, "page": page, "page_size": page_size}
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


def assign_role(db: Session, user_id: int, role: str, actor: User | None = None):
    try:
        target = db.get(User, user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
        if actor is not None and target.id == actor.id:
            raise HTTPException(status_code=409, detail="Không thể tự đổi vai trò của chính mình.")
        if target.role == Role.ADMIN.value:
            raise HTTPException(status_code=409, detail="Không thể đổi vai trò của quản trị viên qua giao diện.")
        if role == Role.ADMIN.value:
            raise HTTPException(status_code=422, detail="Không thể gán vai trò quản trị viên qua giao diện.")
        if target.role == role:
            return target, None
        if target.role == Role.LANDLORD.value and (
            db.scalar(select(Property.id).where(Property.owner_id == target.id)) is not None
            or db.scalar(select(TenantProfile.id).where(TenantProfile.landlord_id == target.id)) is not None
        ):
            raise HTTPException(
                status_code=409,
                detail="Chủ nhà đang sở hữu khu trọ hoặc hồ sơ khách thuê, không thể đổi vai trò.",
            )
        if target.role == Role.MANAGER.value:
            revoked = db.execute(delete(PropertyManager).where(PropertyManager.user_id == target.id)).rowcount
            target.role = role
            save(db, target)
            return target, revoked
        if (
            target.role == Role.TENANT.value
            and db.scalar(select(TenantProfile.id).where(TenantProfile.user_id == target.id)) is not None
        ):
            raise HTTPException(
                status_code=409,
                detail="Tài khoản đang liên kết với hồ sơ khách thuê, hãy gỡ liên kết trước.",
            )
        target.role = role
        save(db, target)
        return target, None
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể truy cập database. Vui lòng thử lại sau.") from exc
