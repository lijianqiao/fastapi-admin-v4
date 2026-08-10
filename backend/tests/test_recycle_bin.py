"""回收站：列表、恢复、永久删除回归测试。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User

pytestmark = pytest.mark.asyncio

type Headers = dict[str, str]


async def test_user_recycle_restore_and_purge(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
) -> None:
    user = User(
        username="trashed_user",
        email="trashed-user@example.com",
        hashed_password=hash_password("trashedpassword123"),
        nickname="回收站用户",
    )
    db_session.add(user)
    await db_session.commit()
    user_id = user.id

    delete_response = await client.delete(f"/api/v1/users/{user_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text

    listed = await client.get("/api/v1/users/deleted", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == user_id for item in listed.json()["data"]["items"])

    restored = await client.post(f"/api/v1/users/{user_id}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["username"] == "trashed_user"
    assert await db_session.scalar(select(User.is_deleted).where(User.id == user_id)) is False

    delete_again = await client.delete(f"/api/v1/users/{user_id}", headers=auth_headers)
    assert delete_again.status_code == 200, delete_again.text

    purged = await client.delete(f"/api/v1/users/{user_id}/purge", headers=auth_headers)
    assert purged.status_code == 200, purged.text
    assert await db_session.scalar(select(User.id).where(User.id == user_id)) is None


async def test_role_recycle_restore_and_purge(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
) -> None:
    role = Role(name="回收站角色", description="待恢复")
    db_session.add(role)
    await db_session.commit()
    role_id = role.id

    delete_response = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)
    assert delete_response.status_code == 200, delete_response.text

    listed = await client.get("/api/v1/roles/deleted", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == role_id for item in listed.json()["data"]["items"])

    # 软删占坑：同名创建应仍冲突
    conflict = await client.post(
        "/api/v1/roles",
        json={"name": "回收站角色", "description": "冲突"},
        headers=auth_headers,
    )
    assert conflict.status_code == 409, conflict.text

    restored = await client.post(f"/api/v1/roles/{role_id}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    assert await db_session.scalar(select(Role.is_deleted).where(Role.id == role_id)) is False

    delete_again = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)
    assert delete_again.status_code == 200, delete_again.text

    purged = await client.delete(f"/api/v1/roles/{role_id}/purge", headers=auth_headers)
    assert purged.status_code == 200, purged.text
    assert await db_session.scalar(select(Role.id).where(Role.id == role_id)) is None

    # 硬删后同名可重建
    recreated = await client.post(
        "/api/v1/roles",
        json={"name": "回收站角色", "description": "重建"},
        headers=auth_headers,
    )
    assert recreated.status_code == 201, recreated.text


async def test_permission_recycle_restore_and_purge(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: Headers,
) -> None:
    permission = Permission(
        name="回收站权限",
        code="recycle:demo",
        module="回收站测试",
    )
    db_session.add(permission)
    await db_session.commit()
    permission_id = permission.id

    delete_response = await client.delete(
        f"/api/v1/permissions/{permission_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 200, delete_response.text

    listed = await client.get("/api/v1/permissions/deleted", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == permission_id for item in listed.json()["data"]["items"])

    restored = await client.post(
        f"/api/v1/permissions/{permission_id}/restore",
        headers=auth_headers,
    )
    assert restored.status_code == 200, restored.text
    assert (
        await db_session.scalar(select(Permission.is_deleted).where(Permission.id == permission_id))
        is False
    )

    delete_again = await client.delete(
        f"/api/v1/permissions/{permission_id}",
        headers=auth_headers,
    )
    assert delete_again.status_code == 200, delete_again.text

    purged = await client.delete(
        f"/api/v1/permissions/{permission_id}/purge",
        headers=auth_headers,
    )
    assert purged.status_code == 200, purged.text
    assert (
        await db_session.scalar(select(Permission.id).where(Permission.id == permission_id)) is None
    )


async def test_purge_active_record_returns_404(
    client: AsyncClient,
    auth_headers: Headers,
    test_role: Role,
) -> None:
    response = await client.delete(f"/api/v1/roles/{test_role.id}/purge", headers=auth_headers)
    assert response.status_code == 404, response.text
