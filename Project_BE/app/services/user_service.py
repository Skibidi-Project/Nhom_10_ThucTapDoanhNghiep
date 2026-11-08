from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate, UserLogin

password_hasher = PasswordHasher()


def register_user(db: Session, data: UserCreate) -> User:
    try:
        existing = db.scalar(select(User).where(or_(User.email == str(data.email), User.phone == data.phone)))
        if existing:
            raise HTTPException(status_code=409, detail="Email hoặc số điện thoại đã được sử dụng.")
        user = User(
            full_name=data.full_name, email=str(data.email), phone=data.phone,
            password_hash=password_hasher.hash(data.password),
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
