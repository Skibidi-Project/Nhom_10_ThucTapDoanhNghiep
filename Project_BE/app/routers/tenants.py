from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import TenantCreate, TenantResponse, TenantUpdate
from app.services import tenant_service
from app.services.db_util import save

router = APIRouter(
    prefix="/api/tenants",
    tags=["Tenants"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.get("", response_model=list[TenantResponse])
def read_tenants(
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return tenant_service.list_tenants(db, user)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: TenantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return tenant_service.create_tenant(db, user, data)


@router.get("/{tenant_id}", response_model=TenantResponse)
def read_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return tenant_service.read_tenant(db, user, tenant_id)


@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return tenant_service.update_tenant(db, user, tenant_id, data)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    tenant_service.delete_tenant(db, user, tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


MAX_ID_PHOTO_BYTES = 2 * 1024 * 1024


async def read_photo_upload(request: Request) -> tuple[bytes, str]:
    mime = request.headers.get("content-type", "")
    signatures = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n"}
    if mime not in signatures:
        raise HTTPException(status_code=415, detail="Chỉ hỗ trợ ảnh JPEG hoặc PNG.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > MAX_ID_PHOTO_BYTES:
            raise HTTPException(status_code=413, detail="Ảnh CCCD tối đa 2 MB.")
        content.extend(chunk)
    if not content.startswith(signatures[mime]):
        raise HTTPException(status_code=415, detail="Nội dung ảnh không khớp định dạng.")
    return bytes(content), mime


@router.put("/{tenant_id}/id-photo", status_code=status.HTTP_204_NO_CONTENT)
def upload_id_photo(
    tenant_id: int,
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
    upload: tuple[bytes, str] = Depends(read_photo_upload),
    db: Session = Depends(get_db),
):
    tenant = tenant_service.read_tenant(db, user, tenant_id)
    tenant.id_photo, tenant.id_photo_type = upload
    save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{tenant_id}/id-photo")
def download_id_photo(
    tenant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    tenant = tenant_service.read_tenant(db, user, tenant_id)
    if tenant.id_photo is None:
        raise HTTPException(status_code=404, detail="Hồ sơ chưa có ảnh CCCD.")
    extension = "png" if tenant.id_photo_type == "image/png" else "jpg"
    return Response(
        tenant.id_photo,
        media_type=tenant.id_photo_type,
        headers={
            "Content-Disposition": f'attachment; filename="cccd-{tenant.id}.{extension}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{tenant_id}/id-photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_id_photo(
    tenant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    tenant = tenant_service.read_tenant(db, user, tenant_id)
    tenant.id_photo = None
    tenant.id_photo_type = None
    save(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
