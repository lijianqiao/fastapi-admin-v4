"""Shared request/response models and reusable field types."""

from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)

PositiveId = Annotated[int, Field(gt=0)]


def _strip_casefold(value: object) -> object:
    return value.strip().casefold() if isinstance(value, str) else value


Username = Annotated[
    str,
    BeforeValidator(_strip_casefold),
    Field(min_length=3, max_length=50, pattern=r"^[a-z0-9][a-z0-9_.-]+$"),
]
NormalizedEmail = Annotated[EmailStr, AfterValidator(str.casefold)]
Password = Annotated[str, Field(min_length=8, max_length=128)]
PermissionCode = Annotated[
    str,
    BeforeValidator(_strip_casefold),
    Field(min_length=3, max_length=100, pattern=r"^[a-z][a-z0-9_-]*:[a-z][a-z0-9_-]*$"),
]


class ApiModel(BaseModel):
    """Strict request model with normalized strings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PartialUpdate(ApiModel):
    """PATCH body: at least one field, and explicitly sent fields must not be null."""

    @model_validator(mode="after")
    def reject_empty_or_null(self) -> Self:
        null_fields = sorted(name for name in self.model_fields_set if getattr(self, name) is None)
        if null_fields:
            raise ValueError(f"字段不能为 null: {', '.join(null_fields)}")
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


class ResponseModel(BaseModel):
    """Response model populated from ORM objects or mappings."""

    model_config = ConfigDict(from_attributes=True)


class PaginatedData[T](BaseModel):
    """A stable page of typed items."""

    items: list[T] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class ResponseEnvelope[T](BaseModel):
    """Uniform API response envelope."""

    code: int
    data: T | None = None
    message: str


def success_response[T](
    data: T | None = None,
    *,
    message: str = "success",
    code: int = 200,
) -> ResponseEnvelope[T]:
    """Create a typed success response."""

    return ResponseEnvelope(code=code, data=data, message=message)


def paginated_response[T](
    items: list[T],
    total: int,
    page: int,
    page_size: int,
) -> ResponseEnvelope[PaginatedData[T]]:
    """Create a typed paginated response."""

    data: PaginatedData[T] = PaginatedData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return ResponseEnvelope(code=200, data=data, message="success")


def unique_ids(values: list[int]) -> list[int]:
    """Deduplicate identifiers while preserving request order."""

    return list(dict.fromkeys(values))
