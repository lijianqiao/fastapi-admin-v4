"""User request and response models."""

from datetime import datetime

from pydantic import ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.common import ApiModel, PositiveId, unique_ids
from app.schemas.role import RoleResponse


class UserCreate(ApiModel):
    """Create a user without implicitly assigning privileged roles."""

    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9][a-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(default="", max_length=50)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().casefold()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).casefold()


class UserUpdate(ApiModel):
    """Partially update mutable user fields."""

    email: EmailStr | None = None
    nickname: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).casefold() if value is not None else None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> UserUpdate:
        null_fields = {name for name in self.model_fields_set if getattr(self, name) is None}
        if null_fields:
            names = ", ".join(sorted(null_fields))
            raise ValueError(f"字段不能为 null: {names}")
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


class UserResponse(ApiModel):
    """Public user representation."""

    id: int
    username: str
    email: str
    nickname: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


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

    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(ApiModel):
    """Change the current user's password."""

    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def require_new_password(self) -> ChangePasswordRequest:
        if self.old_password == self.new_password:
            raise ValueError("新密码不能与旧密码相同")
        return self


class UpdateProfileRequest(ApiModel):
    """Partially update the current user's profile."""

    nickname: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        return str(value).casefold() if value is not None else None

    @model_validator(mode="after")
    def reject_empty_update(self) -> UpdateProfileRequest:
        null_fields = {name for name in self.model_fields_set if getattr(self, name) is None}
        if null_fields:
            names = ", ".join(sorted(null_fields))
            raise ValueError(f"字段不能为 null: {names}")
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self
