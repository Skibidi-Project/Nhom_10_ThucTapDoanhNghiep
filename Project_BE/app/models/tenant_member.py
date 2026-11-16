from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class TenantMember(Base):
    __tablename__ = "contract_members"
    __table_args__ = {"mysql_charset": "utf8mb4"}

    contract_id: Mapped[int] = mapped_column(
        ForeignKey("rental_contracts.id"), primary_key=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"), primary_key=True, index=True
    )
