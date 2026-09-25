"""仪表盘统计 Schema。"""

from datetime import datetime

from pydantic import Field

from app.schemas.common import ResponseModel


class DashboardStats(ResponseModel):
    """仪表盘统计数据。"""

    user_count: int = Field(default=0, description="用户总数")
    role_count: int = Field(default=0, description="角色总数")
    permission_count: int = Field(default=0, description="权限总数")
    active_user_count: int = Field(default=0, description="启用用户数")


class RecentLoginItem(ResponseModel):
    """最近登录记录。"""

    id: int
    user_id: int | None = None
    username: str | None = None
    action: str
    ip: str
    created_at: datetime


class DashboardData(ResponseModel):
    """仪表盘完整数据。"""

    stats: DashboardStats
    recent_logs: list[RecentLoginItem] = Field(default_factory=list)
