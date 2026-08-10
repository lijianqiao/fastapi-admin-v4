"""Permission request and response models."""

from datetime import datetime

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common import ApiModel


class PermissionCreate(ApiModel):
    """Create a permission."""

    name: str = Field(min_length=1, max_length=100)
    code: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_-]*:[a-z][a-z0-9_-]*$",
    )
    module: str = Field(default="", max_length=50)
    description: str = Field(default="", max_length=500)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().casefold()


class PermissionUpdate(ApiModel):
    """Partially update a permission."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(
        default=None,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_-]*:[a-z][a-z0-9_-]*$",
    )
    module: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().casefold()

    @model_validator(mode="after")
    def reject_empty_update(self) -> PermissionUpdate:
        null_fields = {name for name in self.model_fields_set if getattr(self, name) is None}
        if null_fields:
            names = ", ".join(sorted(null_fields))
            raise ValueError(f"字段不能为 null: {names}")
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


class PermissionResponse(ApiModel):
    """Public permission representation."""

    id: int
    name: str
    code: str
    module: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
