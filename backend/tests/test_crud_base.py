"""Shared CRUD primitives: whitelist updates, pagination and the recycle bin."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.permission import permission_crud
from app.crud.role import role_crud
from app.crud.user import user_crud
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def test_apply_update_ignores_fields_outside_the_whitelist() -> None:
    user = User(
        username="u",
        email="u@example.com",
        hashed_password="h",
        nickname="old",
        is_superuser=False,
    )

    user_crud.apply_update(
        user,
        {"nickname": "new", "is_superuser": True, "hashed_password": "x"},
    )

    assert (user.nickname, user.is_superuser, user.hashed_password) == ("new", False, "h")


async def test_paginate_counts_before_slicing(db_session: AsyncSession) -> None:
    db_session.add_all([Permission(name=f"p{i}", code=f"page:item{i}") for i in range(3)])
    await db_session.commit()

    items, total = await permission_crud.paginate(
        db_session,
        select(Permission).where(Permission.code.like("page:%")),
        order_by=(Permission.code.asc(),),
        skip=1,
        limit=1,
    )

    assert total == 3
    assert [item.code for item in items] == ["page:item1"]


async def test_recycle_bin_search_uses_search_columns(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Role(name="回收站甲", is_deleted=True),
            Role(name="其他角色", is_deleted=True),
            Role(name="回收站乙"),
        ]
    )
    await db_session.commit()

    roles, total = await role_crud.get_deleted_multi(
        db_session,
        search="回收站",
        skip=0,
        limit=10,
    )

    assert total == 1
    assert [role.name for role in roles] == ["回收站甲"]


async def test_restore_and_hard_delete_only_touch_recycled_rows(
    db_session: AsyncSession,
) -> None:
    live = Permission(name="在用", code="live:item")
    trashed = Permission(name="回收", code="trash:item", is_deleted=True)
    db_session.add_all([live, trashed])
    await db_session.commit()

    assert await permission_crud.get_deleted(db_session, live.id) is None
    assert await permission_crud.restore(db_session, live.id) is None
    assert await permission_crud.hard_delete(db_session, live.id) is False

    restored = await permission_crud.restore(db_session, trashed.id)
    assert restored is not None
    assert restored.is_deleted is False
    await db_session.commit()
