from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.db.database import engine, init_db
from app.routers import (
    auth,
    billing,
    buildings,
    contracts,
    expenses,
    properties,
    room_type,
    service_assignments,
    tenants,
    users,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(
    title="FastAPI Auth Minimal",
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(buildings.property_router)
app.include_router(buildings.router)
app.include_router(properties.router)
app.include_router(properties.room_router)
app.include_router(tenants.router)
app.include_router(contracts.router)
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
