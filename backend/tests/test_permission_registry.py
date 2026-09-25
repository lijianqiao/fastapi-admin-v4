"""The code-level permission registry is the single source of truth."""

import re
from pathlib import Path

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from app.core.deps import PermissionChecker
from app.core.permissions import PERMISSION_META, SYSTEM_PERMISSION_CODES, Perm
from app.main import app

FRONTEND_CONSTANTS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "constants.ts"
)


def _required_permissions(dependant: Dependant) -> set[str]:
    found: set[str] = set()
    for dependency in dependant.dependencies:
        if isinstance(dependency.call, PermissionChecker):
            found.add(dependency.call.code)
        found |= _required_permissions(dependency)
    return found


def test_every_permission_has_metadata() -> None:
    assert set(PERMISSION_META) == set(Perm)
    assert {perm.value for perm in Perm} == SYSTEM_PERMISSION_CODES


def test_routes_use_exactly_the_registered_permissions() -> None:
    # FastAPI 0.141 把 include_router 收成惰性 _IncludedRouter，
    # app.routes 顶层不再直接展开 APIRoute。
    used: set[str] = set()
    for context in iter_route_contexts(app.routes):
        route = context.original_route
        if isinstance(route, APIRoute):
            used |= _required_permissions(route.dependant)

    assert used == SYSTEM_PERMISSION_CODES


def test_frontend_permission_constants_match_registry() -> None:
    if not FRONTEND_CONSTANTS.exists():
        pytest.skip("frontend sources are not present in this checkout")
    source = FRONTEND_CONSTANTS.read_text(encoding="utf-8")
    block = source.split("export const PERMISSIONS", 1)[1].split("} as const", 1)[0]

    assert set(re.findall(r'"([a-z_]+:[a-z_]+)"', block)) == SYSTEM_PERMISSION_CODES
