"""User request and response models."""

from datetime import datetime
from typing import Self

from pydantic import Field, field_validator, model_validator

from app.schemas.common import (
    ApiModel,
    NormalizedEmail,
    PartialUpdate,
    Password,
    PositiveId,
    ResponseModel,
    Username,
    unique_ids,
)
from app.schemas.role import RoleResponse


class UserCreate(ApiModel):
    """Create a user without implicitly assigning privileged roles."""

    username: Username
    email: NormalizedEmail
    password: Password
    nickname: str = Field(default="", max_length=50)


class UserUpdate(PartialUpdate):
    """Partially update mutable user fields."""

    email: NormalizedEmail | None = None
    nickname: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class UserResponse(ResponseModel):
    """Public user representation."""

    id: int
    username: str
    email: str
    nickname: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class UserWithRoles(UserResponse):
    """User representation including active roles."""

    roles: list[RoleResponse] = Field(default_factory=list)


class CurrentUserResponse(UserWithRoles):
    """Own-profile representation carrying the effective permission codes.

    The client cannot derive these from ``roles`` alone, so the flattened set of
    codes granted through active roles is returned explicitly. A superuser passes
    every check regardless of what this list contains.
    """

    permissions: list[str] = Field(default_factory=list)


class AssignRolesRequest(ApiModel):
    """Replace a user's complete role set."""

    role_ids: list[PositiveId] = Field(default_factory=list, max_length=100)

    @field_validator("role_ids")
    @classmethod
    def deduplicate_ids(cls, values: list[int]) -> list[int]:
        return unique_ids(values)


class AdminResetPasswordRequest(ApiModel):
    """Administrator sets a new password for another user without the old one."""

    new_password: Password


class ChangePasswordRequest(ApiModel):
    """Change the current user's password."""

    old_password: str = Field(min_length=1, max_length=128)
    new_password: Password

    @model_validator(mode="after")
    def require_new_password(self) -> Self:
        if self.old_password == self.new_password:
            raise ValueError("新密码不能与旧密码相同")
        return self


class UpdateProfileRequest(PartialUpdate):
    """Partially update the current user's profile."""

    nickname: str | None = Field(default=None, max_length=50)
    email: NormalizedEmail | None = None
