from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ServiceAssignment(Base):
    __tablename__ = "service_assignments"
    __table_args__ = (
        CheckConstraint("(room_id IS NOT NULL) <> (contract_id IS NOT NULL)", name="ck_service_assignment_target_xor"),
        UniqueConstraint("room_id", "service_code", name="uq_room_service_assignment"),
        UniqueConstraint("contract_id", "service_code", name="uq_contract_service_assignment"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_code: Mapped[str] = mapped_column(String(20), nullable=False)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"), nullable=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("rental_contracts.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
