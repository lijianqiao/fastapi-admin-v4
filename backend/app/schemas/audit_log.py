"""审计日志相关 Schema。"""

from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.common import ApiModel


class AuditLogResponse(ApiModel):
    """审计日志响应。"""

    id: int
    user_id: int | None = None
    username: str | None = None
    action: str
    target: str
    detail: str
    ip: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogCreate(ApiModel):
    """审计日志创建（内部使用）。"""

    user_id: int | None = None
    action: str = Field(min_length=1, max_length=50)
    target: str = Field(default="", max_length=255)
    detail: str = Field(default="", max_length=4000)
    ip: str = Field(default="", max_length=45)
