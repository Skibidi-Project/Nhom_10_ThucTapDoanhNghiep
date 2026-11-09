import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from app.core.rbac import UNAUTHENTICATED

ALGORITHM = "HS256"
TOKEN_HOURS = 24


def _secret() -> str:
    return os.getenv("JWT_SECRET", "dev-change-me")


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, _secret(), algorithm=ALGORITHM)


def read_user_id(token: str) -> int:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=UNAUTHENTICATED,
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise credentials_error from exc
