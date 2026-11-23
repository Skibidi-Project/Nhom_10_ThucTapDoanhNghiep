"""US-31: deterministic demo fixtures in a separate SQLite database."""
import argparse
import calendar
import getpass
from datetime import date, timedelta
from pathlib import Path

from argon2 import PasswordHasher
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.db.database import Base
import app.models
import app.models.room_type
from app.models.user import User
from app.models.boarding import (
    Property, Room, TenantProfile, Contract, UtilityReading,
    UtilityPriceHistory, PropertyServicePrice,
)

EMAIL = "landlord.us31@example.com"


def month_start(value):
    try:
        result = date.fromisoformat(value + "-01")
        if result.strftime("%Y-%m") != value:
            raise ValueError
        return result
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Tháng phải có dạng YYYY-MM.") from exc


def demo_engine(path):
    engine = create_engine("sqlite:///" + str(Path(path).resolve()))
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    return engine


def seed(engine, month, password):
    """Create once in one transaction; reruns preserve all demo edits."""
    if len(password) < 8:
        raise ValueError("Mật khẩu phải có ít nhất 8 ký tự.")
    first = month.replace(day=1)
    previous = (first - timedelta(days=1)).replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        owner = db.scalar(select(User).where(User.email == EMAIL))
        if owner is not None:
            # A rerun must never reset credentials or overwrite edited demo data.
            return False
        if any(db.execute(select(table).limit(1)).first() is not None
               for table in Base.metadata.sorted_tables):
            raise ValueError("Database có dữ liệu khác. Hãy chọn file demo mới.")
        owner = User(full_name="Chủ trọ Demo US31", email=EMAIL,
                     role="landlord", password_hash=PasswordHasher().hash(password))
        db.add(owner)
        db.flush()
        properties = []
        for name, address in [
            ("US31 - Khu trọ An Bình", "Dữ liệu giả lập - Đắk Lắk"),
            ("US31 - Khu trọ Bình Minh", "Dữ liệu giả lập - Hà Nội"),
        ]:
            prop = Property(owner_id=owner.id, name=name, address=address,
                            electricity_unit_price=3500, water_unit_price=15000,
                            service_unit_price=0)
            db.add(prop)
            db.flush()
            properties.append(prop)
            for utility, unit, price in [
                ("electricity", "kwh", 3500), ("water", "m3", 15000),
            ]:
                db.add(PropertyServicePrice(property_id=prop.id, service_code=utility,
                                            billing_unit=unit, unit_price=price))
                db.add(UtilityPriceHistory(
                    property_id=prop.id, utility=utility, unit_price=price,
                    valid_from=previous, valid_to=last, created_by=owner.id,
                    evidence="Thỏa thuận giả lập US31, chỉ dùng test/demo.",
                ))
        for index, (property_index, number, rent, occupied) in enumerate([
            (0, "A101", 2000000, True),
            (0, "A102", 2200000, True),
            (0, "A103", 2400000, False),
            (1, "B101", 2500000, True),
            (1, "B102", 2700000, False),
        ], start=1):
            room = Room(property_id=properties[property_index].id,
                        room_number=number, area_sqm=20 + index * 2,
                        base_rent=rent, status="occupied" if occupied else "available")
            db.add(room)
            db.flush()
            if occupied:
                tenant = TenantProfile(
                    landlord_id=owner.id, created_by=owner.id,
                    full_name=f"Người thuê mẫu {number}",
                    phone=f"09000310{index:02d}", id_number=f"000000310{index:03d}",
                    email=f"tenant.{number.lower()}.us31@example.com",
                    hometown="Địa chỉ giả lập",
                )
                db.add(tenant)
                db.flush()
                db.add(Contract(
                    room_id=room.id, tenant_id=tenant.id, created_by=owner.id,
                    start_date=previous, end_date=last + timedelta(days=365),
                    monthly_rent=rent, deposit=rent, deposit_status="paid",
                    payment_cycle_months=1, status="active",
                ))
            # Vacant rooms have unchanged meters; occupied rooms consume 50 kWh/5 m3.
            for utility, initial, usage in [
                ("electricity", 100 * index, 50 if occupied else 0),
                ("water", 10 * index, 5 if occupied else 0),
            ]:
                for offset, period in enumerate([previous, first]):
                    db.add(UtilityReading(
                        room_id=room.id, utility_type=utility,
                        period=period.strftime("%Y-%m"),
                        previous_reading=initial + offset * usage,
                        current_reading=initial + (offset + 1) * usage,
                        recorded_by=owner.id,
                    ))
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path,
                        default=Path(__file__).resolve().parent / "us31_demo.db",
                        help="File SQLite demo riêng; không sử dụng DATABASE_URL/.env.")
    parser.add_argument("--month", type=month_start, default=date.today().replace(day=1),
                        help="Tháng thứ hai (YYYY-MM), mặc định tháng hiện tại.")
    args = parser.parse_args()
    engine = demo_engine(args.database)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            exists = db.scalar(select(User.id).where(User.email == EMAIL)) is not None
        password = "unused-on-rerun" if exists else getpass.getpass("Đặt mật khẩu demo (ít nhất 8 ký tự): ")
        created = seed(engine, args.month, password)
        print("Đã tạo dữ liệu US31." if created else "Bộ US31 đã tồn tại; giữ nguyên dữ liệu và mật khẩu.")
        with Session(engine) as db:
            periods = list(db.scalars(select(UtilityReading.period).distinct().order_by(UtilityReading.period)))
        print("Database:", args.database.resolve())
        print("Email:", EMAIL)
        print("Các kỳ điện nước:", ", ".join(periods))
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
