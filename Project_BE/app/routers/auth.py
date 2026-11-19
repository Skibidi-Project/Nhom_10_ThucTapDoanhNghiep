from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override
from app.core.security import create_access_token
from app.db.database import get_db
from app.schemas.user import LoginResponse, UserCreate, UserLogin, UserResponse
from app.services.user_service import login_user, register_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(block_privilege_override)],
)
def register(data: UserCreate, db: Session = Depends(get_db)):
    return register_user(db, data)


@router.post("/login", response_model=LoginResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = login_user(db, data)
    return LoginResponse(
        message="Đăng nhập thành công",
        access_token=create_access_token(user.id),
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )
