"""Asynchronous user repository."""

from collections.abc import Iterable, Sequence

from sqlalchemy import Exists, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.crud.base import ModelData, RelatedObjectsNotFoundError, SoftDeleteCRUD, contains_pattern
from app.models.permission import Permission
from app.models.role import Role, role_permissions
from app.models.user import User, user_roles


class CRUDUser(SoftDeleteCRUD[User]):
    """Data access for users and their RBAC assignments."""

    model = User
    updatable_fields = frozenset({"email", "nickname", "is_active"})
    search_columns = ("username", "email")

    def load_options(self) -> Sequence[ExecutableOption]:
        return (selectinload(User.roles.and_(Role.is_deleted.is_(False))),)

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

    async def get_role_ids(self, db: AsyncSession, user_id: int) -> set[int]:
        """Return every role ID currently associated with a user."""
        result = await db.execute(
            select(user_roles.c.role_id).where(user_roles.c.user_id == user_id)
        )
        return set(result.scalars().all())

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
        """Create an unprivileged user from an already-hashed password."""
        user = User(**dict(obj_data))
        user.roles = []
        db.add(user)
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

        return await self.paginate(
            db,
            stmt,
            order_by=(User.id.asc(),),
            skip=skip,
            limit=limit,
        )

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

    async def lock_active_superuser_ids(self, db: AsyncSession) -> list[int]:
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

    async def lock_active(self, db: AsyncSession, user_id: int) -> User | None:
        """Lock an active user row with FOR NO KEY UPDATE for a caller-owned write."""
        stmt = (
            select(User)
            .where(User.id == user_id, User.is_deleted.is_(False))
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_password_hash(self, db: AsyncSession, user_id: int) -> str | None:
        """Read the current password hash of an active user without locking."""
        hashed_password: str | None = await db.scalar(
            select(User.hashed_password).where(User.id == user_id, User.is_deleted.is_(False))
        )
        return hashed_password


user_crud = CRUDUser()
