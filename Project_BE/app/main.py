from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect

from app.db.database import Base, engine, init_db
from app.routers import (
    auth,
    billing,
    buildings,
    contracts,
    dashboard,
    expenses,
    properties,
    room_type,
    service_assignments,
    tenants,
    users,
    utility_pricing,
)


def _payment_idempotency_schema_ready(columns: set[str], uniques: list[dict]) -> bool:
    expected = {'invoice_id', 'recorded_by', 'idempotency_key'}
    return {'idempotency_key', 'request_fingerprint'}.issubset(columns) and any(
        unique.get('name') == 'uq_payment_idempotency'
        and set(unique.get('column_names') or []) == expected
        for unique in uniques
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Existing MySQL databases must be migrated explicitly before startup DDL.
    if engine.dialect.name == 'mysql':
        # Nạp toàn bộ Model để SQLAlchemy nhận diện các bảng.
        import app.models

        # Chỉ tạo những bảng chưa tồn tại, giữ nguyên bảng đã có.
        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        if inspector.has_table('invoices'):
            columns = {column['name'] for column in inspector.get_columns('invoices')}
            if 'due_date' not in columns or not inspector.has_table('invoice_due_date_history'):
                raise RuntimeError('US-25 migration is required before starting this existing database.')
        if inspector.has_table('payments'):
            payment_columns = {column['name'] for column in inspector.get_columns('payments')}
            uniques = inspector.get_unique_constraints('payments')
            if not _payment_idempotency_schema_ready(payment_columns, uniques):
                raise RuntimeError('US-24 idempotency migration is required before starting this existing database.')
        if inspector.has_table('invoices'):
            required = {
                'utility_price_history': {'id','property_id','room_id','contract_id','utility','unit_price','valid_from','valid_to','evidence','created_by','created_at'},
                'invoice_utility_snapshots': {'id','invoice_id','utility','price_id','source','previous_reading','current_reading','unit_price','amount'},
                'invoice_service_snapshots': {'id','invoice_id','service_code','source','quantity','unit_price','billing_unit','amount'},
            }
            for table, columns in required.items():
                if not inspector.has_table(table) or not columns.issubset({c['name'] for c in inspector.get_columns(table)}):
                    raise RuntimeError('US-20 pricing migration is required before starting this existing database.')
        # MySQL schemas are managed by reviewed migrations, never by startup.
        # Check the complete mapped schema before serving requests.
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                raise RuntimeError(f'Missing MySQL table {table.name}; apply reviewed migrations before deployment.')
            existing = {column['name'] for column in inspector.get_columns(table.name)}
            missing = sorted(set(table.columns.keys()) - existing)
            if missing:
                raise RuntimeError(f'Missing MySQL columns in {table.name}: {", ".join(missing)}; apply reviewed migrations before deployment.')
    else:
        init_db()
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="FastAPI Auth Minimal",
    lifespan=lifespan,
)

@app.middleware('http')
async def revalidate_register_assets(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/register/'):
        response.headers['Cache-Control'] = 'no-cache'
    return response

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(utility_pricing.router)
app.include_router(buildings.property_router)
app.include_router(buildings.router)
app.include_router(properties.router)
app.include_router(properties.room_router)
app.include_router(tenants.router)
app.include_router(contracts.router)
app.include_router(dashboard.router)
app.include_router(service_assignments.router)
app.include_router(expenses.router)
app.include_router(billing.invoice_router)
app.include_router(billing.reading_router)
app.include_router(room_type.router)


@app.get("/register", include_in_schema=False)
@app.get("/register/", include_in_schema=False)
async def register_home():
    return RedirectResponse("/register/html/index.html")


@app.get("/register/{page_name}.html", include_in_schema=False)
async def legacy_register_page(page_name: str):
    return RedirectResponse(f"/register/html/{page_name}.html")


app.mount("/register", StaticFiles(directory=Path(__file__).resolve().parents[1] / "register", html=True), name="register")

# Cấu hình CORS cho phép Live Server (port 5500) gọi API
app.add_middleware(
    CORSMiddleware,
    # Hoặc cụ thể ["http://127.0.0.1:5500", "http://localhost:5500"]
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
