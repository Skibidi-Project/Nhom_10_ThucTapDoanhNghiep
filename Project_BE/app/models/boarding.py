from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    electricity_unit_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    water_unit_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    service_unit_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class PropertyManager(Base):
    __tablename__ = "property_managers"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("property_id", "room_number", name="uq_room_number_per_property"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id"), nullable=False)
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    base_rent: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")


class TenantProfile(Base):
    __tablename__ = "tenants"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    landlord_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    id_number: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Contract(Base):
    __tablename__ = "rental_contracts"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    deposit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deposit_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid", server_default="unpaid")
    deposit_returned_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deposit_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    monthly_rent: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_cycle_months: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class UtilityReading(Base):
    __tablename__ = "utility_readings"
    __table_args__ = (
        UniqueConstraint("room_id", "utility_type", "period", name="uq_reading_room_type_period"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    utility_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    previous_reading: Mapped[int] = mapped_column(Integer, nullable=False)
    current_reading: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("contract_id", "period", name="uq_invoice_contract_period"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("rental_contracts.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    rent_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    utility_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False, default="cash")
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
