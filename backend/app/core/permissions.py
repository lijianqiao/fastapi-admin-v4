"""Single source of truth for every permission code checked in code.

Adding a protected endpoint: add a member to ``Perm`` with its metadata, use
``require_permission(Perm.X)`` on the route, add the code to the frontend
``PERMISSIONS`` constant, and run ``init_db.py`` to sync the permissions table.
"""

from dataclasses import dataclass
from enum import StrEnum


class Perm(StrEnum):
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_ASSIGN = "user:assign"
    USER_RESET_PASSWORD = "user:reset_password"
    ROLE_READ = "role:read"
    ROLE_CREATE = "role:create"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"
    ROLE_ASSIGN = "role:assign"
    PERMISSION_READ = "permission:read"
    PERMISSION_CREATE = "permission:create"
    PERMISSION_UPDATE = "permission:update"
    PERMISSION_DELETE = "permission:delete"
    AUDIT_READ = "audit:read"


@dataclass(frozen=True, slots=True)
class PermissionMeta:
    """Default display metadata written when a system permission is created."""

    name: str
    module: str
    description: str


PERMISSION_META: dict[Perm, PermissionMeta] = {
    Perm.USER_READ: PermissionMeta("查看用户", "用户管理", "查看用户列表与详情"),
    Perm.USER_CREATE: PermissionMeta("创建用户", "用户管理", "创建新用户"),
    Perm.USER_UPDATE: PermissionMeta("更新用户", "用户管理", "更新用户资料与状态"),
    Perm.USER_DELETE: PermissionMeta(
        "删除用户", "用户管理", "软删除用户，并管理用户回收站（恢复/永久删除）"
    ),
    Perm.USER_ASSIGN: PermissionMeta("分配角色", "用户管理", "为用户分配角色"),
    Perm.USER_RESET_PASSWORD: PermissionMeta("重置密码", "用户管理", "重置其他用户密码"),
    Perm.ROLE_READ: PermissionMeta("查看角色", "角色管理", "查看角色列表与详情"),
    Perm.ROLE_CREATE: PermissionMeta("创建角色", "角色管理", "创建新角色"),
    Perm.ROLE_UPDATE: PermissionMeta("更新角色", "角色管理", "更新角色信息"),
    Perm.ROLE_DELETE: PermissionMeta(
        "删除角色", "角色管理", "软删除角色，并管理角色回收站（恢复/永久删除）"
    ),
    Perm.ROLE_ASSIGN: PermissionMeta("分配权限", "角色管理", "为角色分配权限"),
    Perm.PERMISSION_READ: PermissionMeta("查看权限", "权限管理", "查看权限列表"),
    Perm.PERMISSION_CREATE: PermissionMeta("创建权限", "权限管理", "创建新权限"),
    Perm.PERMISSION_UPDATE: PermissionMeta("更新权限", "权限管理", "更新权限信息"),
    Perm.PERMISSION_DELETE: PermissionMeta(
        "删除权限", "权限管理", "软删除权限，并管理权限回收站（恢复/永久删除）"
    ),
    Perm.AUDIT_READ: PermissionMeta("查看日志", "审计日志", "查看审计日志"),
}

SYSTEM_PERMISSION_CODES: frozenset[str] = frozenset(perm.value for perm in Perm)
