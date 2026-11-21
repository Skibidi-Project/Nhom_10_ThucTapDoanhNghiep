from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect

from app.db.database import engine, init_db
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
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Existing MySQL databases must be migrated explicitly before startup DDL.
    if engine.dialect.name == 'mysql':
        inspector = inspect(engine)
        if inspector.has_table('invoices'):
            columns = {column['name'] for column in inspector.get_columns('invoices')}
            if 'due_date' not in columns or not inspector.has_table('invoice_due_date_history'):
                raise RuntimeError('US-25 migration is required before starting this existing database.')
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
