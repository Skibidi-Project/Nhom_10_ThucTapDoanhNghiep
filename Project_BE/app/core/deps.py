import json

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.rbac import FORBIDDEN, PRIVILEGE_DENIED, PRIVILEGE_FIELDS, Permission, permissions_for
from app.core.security import read_user_id
from app.db.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def block_privilege_override(request: Request) -> None:
    if request.method not in {"POST", "PUT", "PATCH"}:
        return
    if "application/json" not in request.headers.get("content-type", "").lower():
        return
    raw = await request.body()
    if not raw:
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
        return
    keys = {str(key).lower() for key in data}
    allowed = set()
    if request.method == "PUT" and request.url.path.rstrip("/").endswith("/role"):
        allowed.add("role")
    if keys & (PRIVILEGE_FIELDS - allowed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PRIVILEGE_DENIED)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập hoặc token không hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, read_user_id(credentials.credentials))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa đăng nhập hoặc token không hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permissions(*required: Permission):
    def checker(user: User = Depends(get_current_user)) -> User:
        granted = permissions_for(user.role)
        if not set(required).issubset(granted):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN)
        return user

    return checker
