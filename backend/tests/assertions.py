"""Typed assertion helpers shared by API tests."""

from typing import Any, cast

from httpx import Response

type JsonObject = dict[str, Any]


def response_object(response: Response) -> JsonObject:
    """Return a JSON object and fail with the raw response when it is not one."""
    payload = response.json()
    assert isinstance(payload, dict), response.text
    return cast(JsonObject, payload)


def assert_error(response: Response, status_code: int) -> JsonObject:
    """Assert that transport and envelope status codes match."""
    assert response.status_code == status_code, response.text
    payload = response_object(response)
    assert payload["code"] == status_code
    assert "data" in payload
    assert isinstance(payload.get("message"), str)
    return payload
