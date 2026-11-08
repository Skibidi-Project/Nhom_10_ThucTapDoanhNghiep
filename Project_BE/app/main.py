from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db.database import engine
from app.routers.auth import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        engine.dispose()


app = FastAPI(title="FastAPI Auth Minimal", lifespan=lifespan)
app.include_router(router)
app.mount("/register", StaticFiles(directory=Path(__file__).resolve().parents[1] / "register", html=True), name="register")
