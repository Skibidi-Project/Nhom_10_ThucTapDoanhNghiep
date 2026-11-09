from enum import Enum


class Role(str, Enum):
    """Vai trò trong SRS/SDD. Manager là người quản lý/nhân viên được giao khu trọ."""

    ADMIN = "admin"
    LANDLORD = "landlord"
    MANAGER = "manager"
    TENANT = "tenant"


class Permission(str, Enum):
    USERS_READ = "users.read"
    USERS_ASSIGN_ROLE = "users.assign_role"
    PROFILE_READ = "profile.read"
    PROFILE_UPDATE = "profile.update"
    RENTAL_READ_OWN = "rental.read_own"
    PROPERTY_MANAGE = "property.manage"
    PROPERTY_OPERATE = "property.operate"
    TENANT_MANAGE = "tenant.manage"
    CONTRACT_MANAGE = "contract.manage"
    UTILITY_MANAGE = "utility.manage"
    INVOICE_MANAGE = "invoice.manage"
    INVOICE_READ = "invoice.read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset({
        Permission.USERS_READ,
        Permission.USERS_ASSIGN_ROLE,
        Permission.PROFILE_READ,
        Permission.PROFILE_UPDATE,
        Permission.RENTAL_READ_OWN,
    }),
    Role.LANDLORD: frozenset({
        Permission.PROFILE_READ,
        Permission.PROFILE_UPDATE,
        Permission.RENTAL_READ_OWN,
        Permission.PROPERTY_MANAGE,
        Permission.PROPERTY_OPERATE,
        Permission.TENANT_MANAGE,
        Permission.CONTRACT_MANAGE,
        Permission.UTILITY_MANAGE,
        Permission.INVOICE_MANAGE,
        Permission.INVOICE_READ,
    }),
    Role.MANAGER: frozenset({
        Permission.PROFILE_READ,
        Permission.PROFILE_UPDATE,
        Permission.RENTAL_READ_OWN,
        Permission.PROPERTY_OPERATE,
        Permission.TENANT_MANAGE,
        Permission.CONTRACT_MANAGE,
        Permission.UTILITY_MANAGE,
        Permission.INVOICE_MANAGE,
        Permission.INVOICE_READ,
    }),
    Role.TENANT: frozenset({
        Permission.PROFILE_READ,
        Permission.PROFILE_UPDATE,
        Permission.RENTAL_READ_OWN,
        Permission.INVOICE_READ,
    }),
}

PRIVILEGE_FIELDS = frozenset({
    "role", "roles", "role_id", "is_admin", "owner_id", "landlord_id", "created_by", "recorded_by",
})

UNAUTHENTICATED = "Chưa đăng nhập hoặc token không hợp lệ."
FORBIDDEN = "Bạn không có quyền thực hiện chức năng này."
PRIVILEGE_DENIED = "Không được phép tự thay đổi vai trò hoặc gán quyền sở hữu từ client."


def permissions_for(role: str) -> frozenset[Permission]:
    try:
        return ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return frozenset()
