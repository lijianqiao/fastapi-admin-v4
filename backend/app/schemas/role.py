"""Role request and response models."""

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common import ApiModel, PositiveId, unique_ids
from app.schemas.permission import PermissionResponse


class RoleCreate(ApiModel):
    """Create a role without implicitly assigning permissions."""

    name: str = Field(min_length=1, max_length=50)
    description: str = Field(default="", max_length=500)


class RoleUpdate(ApiModel):
    """Partially update a role."""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_empty_update(self) -> RoleUpdate:
        null_fields = {name for name in self.model_fields_set if getattr(self, name) is None}
        if null_fields:
            names = ", ".join(sorted(null_fields))
            raise ValueError(f"字段不能为 null: {names}")
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


class RoleResponse(ApiModel):
    """Public role representation."""

    id: int
    name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleWithPermissions(RoleResponse):
    """Role representation including active permissions and user count."""

    permissions: list[PermissionResponse] = Field(default_factory=list)
    user_count: int = Field(default=0, ge=0)


class AssignPermissionsRequest(ApiModel):
    """Replace a role's complete permission set."""

    permission_ids: list[PositiveId] = Field(default_factory=list, max_length=200)

    @field_validator("permission_ids")
    @classmethod
    def deduplicate_ids(cls, values: list[int]) -> list[int]:
        return unique_ids(values)
