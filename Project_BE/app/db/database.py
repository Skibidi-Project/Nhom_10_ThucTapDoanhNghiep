import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:123456@localhost/products_db")

engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_user_role_column() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'tenant'"))


def ensure_room_area_column() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("rooms"):
        return
    columns = {column["name"] for column in inspector.get_columns("rooms")}
    if "area_sqm" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE rooms ADD COLUMN area_sqm NUMERIC(6, 2) NULL"))


def ensure_contract_payment_cycle_column() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("rental_contracts"):
        return
    columns = {column["name"] for column in inspector.get_columns("rental_contracts")}
    if "payment_cycle_months" in columns:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE rental_contracts ADD COLUMN payment_cycle_months INT NOT NULL DEFAULT 1")
        )


def ensure_contract_deposit_columns() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("rental_contracts"):
        return
    columns = {column["name"] for column in inspector.get_columns("rental_contracts")}
    with engine.begin() as connection:
        if "deposit_status" not in columns:
            connection.execute(text("ALTER TABLE rental_contracts ADD COLUMN deposit_status VARCHAR(20) NOT NULL DEFAULT 'unpaid'"))
        if "deposit_returned_amount" not in columns:
            connection.execute(text("ALTER TABLE rental_contracts ADD COLUMN deposit_returned_amount INT NOT NULL DEFAULT 0"))
        if "deposit_note" not in columns:
            connection.execute(text("ALTER TABLE rental_contracts ADD COLUMN deposit_note VARCHAR(500) NULL"))


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_user_role_column()
    ensure_room_area_column()
    ensure_contract_payment_cycle_column()
    ensure_contract_deposit_columns()
