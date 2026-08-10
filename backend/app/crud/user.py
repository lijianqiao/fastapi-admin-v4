"""Asynchronous user repository."""

from collections.abc import Iterable

from sqlalchemy import Exists, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password_async, verify_and_update_password
from app.crud.base import CRUDBase, ModelData, RelatedObjectsNotFoundError, contains_pattern
from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.user import User, user_roles


class LastActiveSuperuserError(ValueError):
    """Raised when an operation would remove the final active superuser."""


class CRUDUser(CRUDBase[User]):
    """Data access for users and their RBAC assignments."""

    model = User

    async def get_by_username_any(self, db: AsyncSession, username: str) -> User | None:
        """Return matching username including a recoverable soft-deleted user."""
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email_any(self, db: AsyncSession, email: str) -> User | None:
        """Return matching email including a recoverable soft-deleted user."""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_identifier(self, db: AsyncSession, identifier: str) -> User | None:
        """Read a login candidate without exposing row-lock timing on failures."""
        stmt = select(User).where(
            or_(User.username == identifier, User.email == identifier),
            User.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_identifier_for_update(
        self,
        db: AsyncSession,
        identifier: str,
    ) -> User | None:
        """Reload and lock a successfully verified login candidate."""
        stmt = (
            select(User)
            .where(
                or_(User.username == identifier, User.email == identifier),
                User.is_deleted.is_(False),
            )
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_roles(self, db: AsyncSession, user_id: int) -> User | None:
        """Return an active user with only active roles eagerly loaded."""
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_deleted.is_(False))
            .options(selectinload(User.roles.and_(Role.is_deleted.is_(False))))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_roles_for_update(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> User | None:
        """Lock and return an active user with active roles eagerly loaded."""
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_deleted.is_(False))
            .options(selectinload(User.roles.and_(Role.is_deleted.is_(False))))
            .order_by(User.id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_all_roles_for_update(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> User | None:
        """Lock a user and load every association, including deleted roles.

        Replacement writes must see hidden associations too; otherwise restoring
        a role could unexpectedly restore a relationship that was meant to be
        removed while the role was deleted.
        """
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_deleted.is_(False))
            .options(selectinload(User.roles))
            .order_by(User.id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def authenticate(
        self,
        db: AsyncSession,
        identifier: str,
        password: str,
    ) -> User | None:
        """Verify credentials without blocking the event loop or leaking user existence."""
        candidate = await self.get_by_identifier(db, identifier)
        candidate_hash = candidate.hashed_password if candidate is not None else None
        candidate_is_active = candidate is not None and candidate.is_active
        # Release the read transaction and pooled connection before expensive
        # KDF work. A successful verification is re-read under a row lock below.
        await db.rollback()
        verification = await verify_and_update_password(
            password,
            candidate_hash,
        )
        if candidate is None or not candidate_is_active or not verification.valid:
            return None

        user = await self.get_by_identifier_for_update(db, identifier)
        if user is None or not user.is_active:
            return None

        if user.hashed_password != candidate_hash:
            verification = await verify_and_update_password(password, user.hashed_password)
            if not verification.valid:
                return None

        if verification.updated_hash is not None:
            user.hashed_password = verification.updated_hash
            await db.flush()
        return user

    async def _get_required_roles(
        self,
        db: AsyncSession,
        role_ids: Iterable[int],
    ) -> list[Role]:
        normalized_ids = tuple(dict.fromkeys(role_ids))
        if not normalized_ids:
            return []

        stmt = (
            select(Role)
            .where(
                Role.id.in_(normalized_ids),
                Role.is_deleted.is_(False),
            )
            .order_by(Role.id)
            .with_for_update()
        )
        result = await db.execute(stmt)
        roles_by_id = {role.id: role for role in result.scalars().all()}
        missing_ids = set(normalized_ids) - roles_by_id.keys()
        if missing_ids:
            raise RelatedObjectsNotFoundError("role", missing_ids)
        return [roles_by_id[role_id] for role_id in normalized_ids]

    async def create(self, db: AsyncSession, obj_data: ModelData) -> User:
        """Create an unprivileged user; roles are assigned through a separate operation."""
        data = dict(obj_data)
        password = data.pop("password", None)

        if not isinstance(password, str):
            raise ValueError("创建用户必须提供密码")
        data["hashed_password"] = await hash_password_async(password)

        db_obj = User(**data)
        db_obj.roles = []
        db.add(db_obj)
        await db.flush()
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        id: int,
        obj_data: ModelData,
    ) -> User | None:
        """Update mutable user fields and keep any loaded roles available."""
        deactivating = obj_data.get("is_active") is False
        active_superuser_ids: list[int] = []
        if deactivating:
            active_superuser_ids = await self._lock_active_superuser_ids(db)

        user = await self.get_with_roles_for_update(db, id)
        if user is None:
            return None
        if (
            deactivating
            and user.is_superuser
            and user.is_active
            and not any(user_id != user.id for user_id in active_superuser_ids)
        ):
            raise LastActiveSuperuserError("不能停用最后一个启用的超级管理员")

        mutable_fields = {"email", "nickname", "is_active"}
        for field, value in obj_data.items():
            if field in mutable_fields:
                setattr(user, field, value)
        await db.flush()
        return user

    async def assign_roles(
        self,
        db: AsyncSession,
        user_id: int,
        role_ids: list[int],
    ) -> User | None:
        """Atomically replace all roles after validating the full ID set."""
        user = await self.get_with_all_roles_for_update(db, user_id)
        if user is None:
            return None
        user.roles = await self._get_required_roles(db, role_ids)
        await db.flush()
        return user

    async def get_multi_filtered(
        self,
        db: AsyncSession,
        search: str | None = None,
        is_active: bool | None = None,
        role_id: int | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[User], int]:
        """Return a deterministic page with active roles eagerly loaded."""
        stmt = (
            select(User)
            .where(User.is_deleted.is_(False))
            .options(selectinload(User.roles.and_(Role.is_deleted.is_(False))))
        )

        if search:
            search_pattern = contains_pattern(search)
            stmt = stmt.where(
                or_(
                    User.username.ilike(search_pattern, escape="\\"),
                    User.email.ilike(search_pattern, escape="\\"),
                )
            )

        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))

        if role_id is not None:
            stmt = (
                stmt.join(user_roles)
                .join(
                    Role,
                    Role.id == user_roles.c.role_id,
                )
                .where(Role.id == role_id, Role.is_deleted.is_(False))
            )

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        page_stmt = stmt.order_by(User.id).offset(skip).limit(limit)
        users_result = await db.execute(page_stmt)
        return list(users_result.scalars().unique().all()), total

    async def get_permission_codes(self, db: AsyncSession, user_id: int) -> list[str]:
        """Return permissions granted through active, non-deleted roles only."""
        stmt = (
            select(Permission.code)
            .join(role_permissions, role_permissions.c.permission_id == Permission.id)
            .join(Role, Role.id == role_permissions.c.role_id)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(
                user_roles.c.user_id == user_id,
                Role.is_deleted.is_(False),
                Role.is_active.is_(True),
                Permission.is_deleted.is_(False),
                Permission.is_active.is_(True),
            )
            .distinct()
            .order_by(Permission.code)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def permission_exists(user_id: int, code: str) -> Exists:
        """Build the EXISTS clause granting one permission through active roles.

        Exposed as a clause so callers can fold the authorization check into an
        existing statement instead of paying a second round trip.
        """
        return exists(
            select(Permission.id)
            .join(role_permissions, role_permissions.c.permission_id == Permission.id)
            .join(Role, Role.id == role_permissions.c.role_id)
            .join(user_roles, user_roles.c.role_id == Role.id)
            .where(
                user_roles.c.user_id == user_id,
                Permission.code == code,
                Role.is_deleted.is_(False),
                Role.is_active.is_(True),
                Permission.is_deleted.is_(False),
                Permission.is_active.is_(True),
            )
        )

    async def has_permission(self, db: AsyncSession, user_id: int, code: str) -> bool:
        """Check one permission through active roles without loading the full set."""
        return bool(await db.scalar(select(self.permission_exists(user_id, code))))

    async def has_permission_or_superuser(self, db: AsyncSession, user: User, code: str) -> bool:
        """Return True for a superuser, or a user holding the permission through active roles.

        For endpoints that gate part of a response rather than the whole route
        (so a 403 from ``require_permission`` would be wrong), keeping this
        check here — rather than inline in a route — keeps authorization logic
        in one reusable, testable place.
        """
        if user.is_superuser:
            return True
        return await self.has_permission(db, user.id, code)

    async def _lock_active_superuser_ids(self, db: AsyncSession) -> list[int]:
        """Serialize operations that can remove an active superuser."""
        stmt = (
            select(User.id)
            .where(
                User.is_superuser.is_(True),
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
            .order_by(User.id)
            .with_for_update(key_share=True)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def soft_delete(self, db: AsyncSession, id: int) -> bool:
        """Soft-delete a user while preventing concurrent admin lockout."""
        active_superuser_ids = await self._lock_active_superuser_ids(db)
        user = await self.get_with_roles_for_update(db, id)
        if user is None:
            return False
        if (
            user.is_superuser
            and user.is_active
            and not any(user_id != user.id for user_id in active_superuser_ids)
        ):
            raise LastActiveSuperuserError("不能删除最后一个启用的超级管理员")

        user.is_deleted = True
        await db.flush()
        return True

    async def get_deleted_multi(
        self,
        db: AsyncSession,
        search: str | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[User], int]:
        """Return a page of soft-deleted users for the recycle bin."""
        stmt = (
            select(User)
            .where(User.is_deleted.is_(True))
            .options(selectinload(User.roles.and_(Role.is_deleted.is_(False))))
        )
        if search:
            search_pattern = contains_pattern(search)
            stmt = stmt.where(
                or_(
                    User.username.ilike(search_pattern, escape="\\"),
                    User.email.ilike(search_pattern, escape="\\"),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = (await db.execute(count_stmt)).scalar_one()
        page_stmt = stmt.order_by(User.updated_at.desc(), User.id.desc()).offset(skip).limit(limit)
        users = list((await db.execute(page_stmt)).scalars().unique().all())
        return users, total

    async def restore(self, db: AsyncSession, user_id: int) -> User | None:
        """Restore a soft-deleted user and return it with active roles loaded."""
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_deleted.is_(True))
            .options(selectinload(User.roles.and_(Role.is_deleted.is_(False))))
            .order_by(User.id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            return None
        user.is_deleted = False
        await db.flush()
        return user

    async def hard_delete(self, db: AsyncSession, user_id: int) -> bool:
        """Permanently remove a soft-deleted user and cascaded associations."""
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_deleted.is_(True))
            .order_by(User.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user is None:
            return False
        await db.delete(user)
        await db.flush()
        return True

    async def _lock_for_password_update(self, db: AsyncSession, user_id: int) -> User | None:
        """Lock an active user row ahead of a password write."""
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_deleted.is_(False))
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def change_password(
        self,
        db: AsyncSession,
        user_id: int,
        old_password: str,
        new_password: str,
    ) -> bool:
        """Verify and replace the latest password under one row lock.

        Locking before verification makes two concurrent requests using the same
        old password serialize: after the first commits, the second verifies
        against the new hash and fails. The caller must follow up with
        ``revoke_all_refresh_sessions``, which owns the ``token_version`` bump.
        """
        user = await self._lock_for_password_update(db, user_id)
        if user is None:
            return False

        verification = await verify_and_update_password(old_password, user.hashed_password)
        if not verification.valid:
            return False

        user.hashed_password = await hash_password_async(new_password)
        await db.flush()
        return True

    async def reset_password(
        self,
        db: AsyncSession,
        user_id: int,
        new_password: str,
    ) -> bool:
        """Administrator sets a new password without verifying the old one.

        The caller must follow up with ``revoke_all_refresh_sessions``, which
        owns the ``token_version`` bump, mirroring ``change_password``.
        """
        user = await self._lock_for_password_update(db, user_id)
        if user is None:
            return False

        user.hashed_password = await hash_password_async(new_password)
        await db.flush()
        return True


user_crud = CRUDUser()
