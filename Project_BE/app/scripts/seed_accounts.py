from getpass import getpass
import os
import tempfile
from pathlib import Path
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.rbac import Role
from app.db.database import SessionLocal, init_db
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import password_hasher

DEMO_ACCOUNTS: tuple[tuple[Role, str, str], ...] = (
    (Role.ADMIN, "Quản trị viên", "admin@gmail.com"),
    (Role.LANDLORD, "Chủ nhà", "landlord@gmail.com"),
    (Role.MANAGER, "Quản lý", "manager@gmail.com"),
    (Role.TENANT, "Khách thuê", "tenant@gmail.com"),
)


def main() -> int:
    configured = os.environ.get('DATABASE_URL')
    if not configured:
        raise SystemExit('Cần chỉ rõ DATABASE_URL demo cô lập.')
    url = make_url(configured)
    sqlite_ok = (url.get_backend_name() == 'sqlite' and url.database and
                 Path(url.database).resolve().parent == Path(tempfile.gettempdir()).resolve() and
                 Path(url.database).name.startswith('ministay_business_e2e_'))
    mysql_ok = (url.get_backend_name() == 'mysql' and url.host in ('localhost','127.0.0.1') and
                (url.port or 3306) == 3306 and (url.database or '').startswith('ministay_business_test_'))
    if not (sqlite_ok or mysql_ok):
        raise SystemExit('Từ chối seed: database không phải môi trường demo cô lập.')
    init_db()
    results: list[tuple[str, str]] = []
    failed = False

    with SessionLocal() as db:
        for role, full_name, email in DEMO_ACCOUNTS:
            try:
                existing_user = db.scalar(select(User.id).where(User.email == email))
                if existing_user is not None:
                    results.append((email, "đã tồn tại, bỏ qua"))
                    continue
                password = getpass(f"Mật khẩu demo cho {email}: ")
                data = UserCreate.model_validate({
                    "full_name": full_name,
                    "email": email,
                    "password": password,
                })
                db.add(User(
                    full_name=data.full_name,
                    email=str(data.email),
                    password_hash=password_hasher.hash(data.password),
                    role=role.value,
                ))
                db.commit()
                results.append((email, "đã tạo"))
            except (ValidationError, SQLAlchemyError):
                db.rollback()
                results.append((email, "lỗi, không tạo"))
                failed = True

    print(f"{'Email':<28} Kết quả")
    print("-" * 52)
    for email, result in results:
        print(f"{email:<28} {result}")
    print(
        "Tài khoản này chỉ dùng cho môi trường phát triển/demo."
    )
    if failed:
        print("Có tài khoản chưa tạo được; hãy kiểm tra cấu hình và kết nối database.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
