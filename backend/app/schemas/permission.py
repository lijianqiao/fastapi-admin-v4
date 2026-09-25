"""Permission request and response models."""

from datetime import datetime

from pydantic import Field

from app.schemas.common import ApiModel, PartialUpdate, PermissionCode, ResponseModel


class PermissionCreate(ApiModel):
    """Create a permission."""

    name: str = Field(min_length=1, max_length=100)
    code: PermissionCode
    module: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=500)


class PermissionUpdate(PartialUpdate):
    """Partially update a permission; the code is immutable once created."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    module: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class PermissionResponse(ResponseModel):
    """Public permission representation."""

    id: int
    name: str
    code: str
    module: str
    description: str
    is_active: bool
    is_system: bool
    created_at: datetime
    updated_at: datetime
