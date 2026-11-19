from datetime import datetime

from sqlalchemy import DateTime, Integer, LargeBinary, String, text
from sqlalchemy.dialects.mysql import MEDIUMBLOB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(12), nullable=True)
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary().with_variant(MEDIUMBLOB(), "mysql"), deferred=True)
    avatar_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="tenant", server_default=text("'tenant'"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
