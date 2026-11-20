from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.rbac import Role
from app.db.database import SessionLocal, init_db
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import password_hasher

DEMO_ACCOUNTS: tuple[tuple[Role, str, str, str], ...] = (
    (Role.ADMIN, "Quản trị viên", "admin@gmail.com", "Admin123456"),
    (Role.LANDLORD, "Chủ nhà", "landlord@gmail.com", "Landlord123456"),
    (Role.MANAGER, "Quản lý", "manager@gmail.com", "Manager123456"),
    (Role.TENANT, "Khách thuê", "tenant@gmail.com", "Tenant123456"),
)


def main() -> int:
    init_db()
    results: list[tuple[str, str]] = []
    failed = False

    with SessionLocal() as db:
        for role, full_name, email, password in DEMO_ACCOUNTS:
            try:
                data = UserCreate.model_validate({
                    "full_name": full_name,
                    "email": email,
                    "password": password,
                })
                existing_user = db.scalar(select(User.id).where(User.email == str(data.email)))
                if existing_user is not None:
                    results.append((email, "đã tồn tại, bỏ qua"))
                    continue

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
        "Cảnh báo: Tài khoản demo dùng mật khẩu công khai trong README, chỉ dùng "
        "cho môi trường phát triển/demo, không dùng cho môi trường thật."
    )
    if failed:
        print("Có tài khoản chưa tạo được; hãy kiểm tra cấu hình và kết nối database.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
