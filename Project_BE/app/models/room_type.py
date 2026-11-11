from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class RoomType(Base):
    __tablename__ = "room_types"
    __table_args__ = (
        CheckConstraint("listed_price >= 0", name="ck_room_type_listed_price"),
        {"mysql_charset": "utf8mb4"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    listed_price: Mapped[int] = mapped_column(Integer, nullable=False)


class RoomTypeAssignment(Base):
    """Liên kết riêng để không bổ sung cột vào bảng rooms hiện có."""

    __tablename__ = "room_type_assignments"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="RESTRICT"), primary_key=True)
    room_type_id: Mapped[int] = mapped_column(
        ForeignKey("room_types.id", ondelete="RESTRICT"), nullable=False
    )
