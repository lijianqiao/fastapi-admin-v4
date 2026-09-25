"""Request/response schema behavior locked before the reuse refactor."""

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.common import PaginatedData, ResponseEnvelope
from app.schemas.permission import PermissionCreate, PermissionUpdate
from app.schemas.role import RoleUpdate
from app.schemas.user import UpdateProfileRequest, UserCreate, UserResponse, UserUpdate


def test_username_is_trimmed_and_casefolded() -> None:
    user = UserCreate(username="  Alice.W ", email="A@Example.COM", password="password123")

    assert user.username == "alice.w"
    assert user.email == "a@example.com"


def test_permission_code_is_normalized() -> None:
    permission = PermissionCreate(name="导出", code=" USER:EXPORT ")

    assert permission.code == "user:export"


@pytest.mark.parametrize(
    "model",
    [UserUpdate, RoleUpdate, PermissionUpdate, UpdateProfileRequest],
)
def test_partial_update_rejects_empty_body(model: type[BaseModel]) -> None:
    with pytest.raises(ValidationError, match="至少提供一个要更新的字段"):
        model.model_validate({})


def test_partial_update_rejects_explicit_null() -> None:
    with pytest.raises(ValidationError, match="字段不能为 null: nickname"):
        UserUpdate.model_validate({"nickname": None})


def test_request_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"is_superuser": True})


def test_response_models_ignore_unknown_attributes() -> None:
    user = UserResponse.model_validate(
        {
            "id": 1,
            "username": "a",
            "email": "a@example.com",
            "nickname": "",
            "is_active": True,
            "is_superuser": False,
            "created_at": "2026-09-25T00:00:00Z",
            "updated_at": "2026-09-25T00:00:00Z",
            "hashed_password": "must-not-leak",
        }
    )

    assert "hashed_password" not in user.model_dump()


def test_generic_envelope_validates_nested_items() -> None:
    envelope = ResponseEnvelope[PaginatedData[int]].model_validate(
        {
            "code": 200,
            "data": {"items": [1, 2], "total": 2, "page": 1, "page_size": 10},
            "message": "ok",
        }
    )
    assert envelope.data is not None
    assert envelope.data.items == [1, 2]

    with pytest.raises(ValidationError):
        ResponseEnvelope[PaginatedData[int]].model_validate(
            {
                "code": 200,
                "data": {"items": ["x"], "total": 1, "page": 1, "page_size": 10},
                "message": "ok",
            }
        )
