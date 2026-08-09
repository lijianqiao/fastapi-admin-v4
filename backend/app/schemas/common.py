"""Shared request and response models."""

from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

PositiveId = Annotated[int, Field(gt=0)]


class ApiModel(BaseModel):
    """Strict API-boundary model with normalized strings."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PaginatedData(BaseModel, Generic[T]):
    """A stable page of typed items."""

    items: list[T] = Field(default_factory=list)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)


class ResponseEnvelope(BaseModel, Generic[T]):
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
