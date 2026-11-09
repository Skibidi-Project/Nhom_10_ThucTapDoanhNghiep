from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.database import engine, init_db
from app.routers import auth, billing, contracts, properties, tenants, users


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
app.include_router(properties.router)
app.include_router(properties.room_router)
app.include_router(tenants.router)
app.include_router(contracts.router)
app.include_router(billing.invoice_router)
app.include_router(billing.reading_router)
app.mount("/register", StaticFiles(directory=Path(__file__).resolve().parents[1] / "register", html=True), name="register")
