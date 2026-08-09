"""CRUD 包初始化，导出所有 CRUD 实例。"""

from app.crud.audit_log import audit_log_crud
from app.crud.dashboard import dashboard_crud
from app.crud.permission import permission_crud
from app.crud.role import role_crud
from app.crud.user import user_crud

__all__ = [
    "audit_log_crud",
    "dashboard_crud",
    "permission_crud",
    "role_crud",
    "user_crud",
]
