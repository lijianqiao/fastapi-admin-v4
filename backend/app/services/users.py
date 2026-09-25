"""User-management use cases: business rules, row locks and session revocation.

Functions flush but never commit; the endpoint commits once together with its
audit record. The one deliberate exception is ``release_connection`` before
password hashing, which ends a read-only transaction so no pooled connection is
held while a KDF runs (or while it waits for a free password worker).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import release_connection
from app.core.errors import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password_async, verify_and_update_password
from app.crud.role import role_crud
from app.crud.user import user_crud
from app.models.user import User
from app.schemas.user import UpdateProfileRequest, UserCreate, UserUpdate
from app.services.auth import revoke_all_refresh_sessions
from app.services.guards import ensure_can_manage, ensure_grantable


class LastActiveSuperuserError(ConflictError):
    """Raised when an operation would remove the final active superuser."""


def _ensure_other_active_superuser(
    user: User,
    active_superuser_ids: list[int],
    message: str,
) -> None:
    if user.is_superuser and user.is_active and not any(
        user_id != user.id for user_id in active_superuser_ids
    ):
        raise LastActiveSuperuserError(message)


async def _ensure_email_available(db: AsyncSession, email: str, *, owner_id: int | None) -> None:
    existing = await user_crud.get_by_email_any(db, email)
    if existing is not None and existing.id != owner_id:
        raise ConflictError("邮箱已被占用（包括已删除账户）")


async def _reload_with_roles(db: AsyncSession, user_id: int) -> User:
    user = await user_crud.get_with_roles_for_update(db, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    return user


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """Create an unprivileged user; the password is hashed after the connection is released."""
    if await user_crud.get_by_username_any(db, data.username):
        raise ConflictError("用户名已被占用（包括已删除账户）")
    await _ensure_email_available(db, data.email, owner_id=None)
    await release_connection(db)
    hashed_password = await hash_password_async(data.password)
    return await user_crud.create(
        db,
        {
            "username": data.username,
            "email": data.email,
            "nickname": data.nickname,
            "hashed_password": hashed_password,
        },
    )


async def update_user(db: AsyncSession, actor: User, user_id: int, data: UserUpdate) -> User:
    """Apply an administrator's partial update; disabling revokes every session."""
    changes = data.model_dump(exclude_unset=True)
    disabling = changes.get("is_active") is False
    active_superuser_ids = await user_crud.lock_active_superuser_ids(db) if disabling else []
    user = await user_crud.get_with_roles_for_update(db, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    ensure_can_manage(actor, user)
    if disabling and user.id == actor.id:
        # 停用会递增 token_version 并撤销全部会话族，调用者会被立即踢下线
        raise BadRequestError("不能停用当前登录用户")
    if "email" in changes and changes["email"] != user.email:
        await _ensure_email_available(db, changes["email"], owner_id=user.id)
    if disabling:
        _ensure_other_active_superuser(user, active_superuser_ids, "不能停用最后一个启用的超级管理员")

    user_crud.apply_update(user, changes)
    await db.flush()
    if disabling:
        await revoke_all_refresh_sessions(db, user.id, reason="user_disabled")
        # 撤销时的加锁重读（populate_existing）会让 roles 失效，重新加载响应需要的关系
        user = await _reload_with_roles(db, user.id)
    return user


async def update_profile(db: AsyncSession, user: User, data: UpdateProfileRequest) -> User:
    """Let the current user change their own nickname and email."""
    changes = data.model_dump(exclude_unset=True)
    locked = await _reload_with_roles(db, user.id)
    if "email" in changes and changes["email"] != locked.email:
        await _ensure_email_available(db, changes["email"], owner_id=locked.id)
    user_crud.apply_update(locked, changes)
    await db.flush()
    return locked


async def delete_user(db: AsyncSession, actor: User, user_id: int) -> User:
    """Soft-delete a user and revoke all of their sessions."""
    active_superuser_ids = await user_crud.lock_active_superuser_ids(db)
    user = await user_crud.lock_active(db, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    if user.id == actor.id:
        raise BadRequestError("不能删除当前登录用户")
    ensure_can_manage(actor, user)
    _ensure_other_active_superuser(user, active_superuser_ids, "不能删除最后一个启用的超级管理员")

    user.is_deleted = True
    await db.flush()
    await revoke_all_refresh_sessions(db, user.id, reason="user_deleted")
    return user


async def reset_password(db: AsyncSession, actor: User, user_id: int, new_password: str) -> None:
    """An administrator sets another user's password and revokes that user's sessions."""
    if user_id == actor.id:
        raise BadRequestError("请通过个人中心修改自己的密码")
    target = await user_crud.get(db, user_id)
    if target is None:
        raise NotFoundError("用户不存在")
    ensure_can_manage(actor, target)

    await release_connection(db)
    new_hash = await hash_password_async(new_password)
    user = await user_crud.lock_active(db, user_id)
    if user is None:
        raise NotFoundError("用户不存在")
    user.hashed_password = new_hash
    await db.flush()
    await revoke_all_refresh_sessions(db, user.id, reason="password_reset_by_admin")


async def change_password(
    db: AsyncSession,
    user_id: int,
    old_password: str,
    new_password: str,
) -> bool:
    """Verify and replace a password without running a KDF under the row lock.

    Optimistic scheme, the same as login: read the hash, release the connection,
    verify and hash, then lock and confirm the hash is unchanged. When it changed
    meanwhile (another change, or a login's bcrypt→Argon2 upgrade) the old
    password is re-verified against the latest hash under the lock.
    """
    current_hash = await user_crud.get_password_hash(db, user_id)
    await release_connection(db)
    if current_hash is None:
        return False
    if not (await verify_and_update_password(old_password, current_hash)).valid:
        return False
    new_hash = await hash_password_async(new_password)

    user = await user_crud.lock_active(db, user_id)
    if user is None:
        return False
    if user.hashed_password != current_hash:
        if not (await verify_and_update_password(old_password, user.hashed_password)).valid:
            return False
    user.hashed_password = new_hash
    await db.flush()
    return True


async def assign_roles(db: AsyncSession, actor: User, user_id: int, role_ids: list[int]) -> User:
    """Replace a user's roles under the delegation rules."""
    target = await user_crud.get(db, user_id)
    if target is None:
        raise NotFoundError("用户不存在")
    ensure_can_manage(actor, target)
    if not actor.is_superuser:
        if user_id == actor.id:
            raise ForbiddenError("不能修改自己的角色")
        added_role_ids = set(role_ids) - await user_crud.get_role_ids(db, user_id)
        await ensure_grantable(db, actor, await role_crud.get_permission_codes(db, added_role_ids))
    user = await user_crud.assign_roles(db, user_id, role_ids)
    if user is None:
        raise NotFoundError("用户不存在")
    return user
