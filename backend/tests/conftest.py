"""Shared asynchronous pytest fixtures."""

import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# Configure the application before importing modules that construct the engine/settings.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-at-least-32-characters-long"
os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["LOG_LEVEL"] = "warning"
os.environ["COOKIE_SECURE"] = "false"
os.environ["REGISTRATION_ENABLED"] = "true"
# Pin explicitly so the suite doesn't silently inherit a developer's local .env
# (whose ALLOWED_HOSTS is tuned for real browsers, not httpx's "test" host).
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,test"

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.permission import Permission  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth import login_rate_limiter, registration_rate_limiter  # noqa: E402

type Headers = dict[str, str]
type PermissionData = dict[str, Any]
type LoginUser = Callable[[str, str], Awaitable[Headers]]


@pytest_asyncio.fixture(autouse=True)
async def reset_rate_limiters() -> AsyncIterator[None]:
    """Keep process-local security throttles isolated between tests."""
    await login_rate_limiter.reset()
    await registration_rate_limiter.reset()
    yield
    await login_rate_limiter.reset()
    await registration_rate_limiter.reset()


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Create an isolated in-memory async database for each test."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield one AsyncSession shared by fixtures and the application request."""
    session_factory = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """Yield an in-process client whose requests use isolated sessions."""

    request_session_factory = async_sessionmaker(
        db_engine,
        expire_on_commit=False,
        autoflush=False,
    )

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with request_session_factory() as request_session:
            try:
                yield request_session
            finally:
                if request_session.in_transaction():
                    await request_session.rollback()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            # Simulate a same-origin browser by default, matching what a real
            # frontend sends; CSRF-specific tests override this per-request.
            headers={"Sec-Fetch-Site": "same-origin"},
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_permissions(db_session: AsyncSession) -> list[Permission]:
    """Create the complete permission set used by an administrator role."""
    permission_data: list[PermissionData] = [
        {"name": "查看用户", "code": "user:read", "module": "用户管理"},
        {"name": "创建用户", "code": "user:create", "module": "用户管理"},
        {"name": "更新用户", "code": "user:update", "module": "用户管理"},
        {"name": "删除用户", "code": "user:delete", "module": "用户管理"},
        {"name": "分配角色", "code": "user:assign", "module": "用户管理"},
        {"name": "重置密码", "code": "user:reset_password", "module": "用户管理"},
        {"name": "查看角色", "code": "role:read", "module": "角色管理"},
        {"name": "创建角色", "code": "role:create", "module": "角色管理"},
        {"name": "更新角色", "code": "role:update", "module": "角色管理"},
        {"name": "删除角色", "code": "role:delete", "module": "角色管理"},
        {"name": "分配权限", "code": "role:assign", "module": "角色管理"},
        {"name": "查看权限", "code": "permission:read", "module": "权限管理"},
        {"name": "创建权限", "code": "permission:create", "module": "权限管理"},
        {"name": "更新权限", "code": "permission:update", "module": "权限管理"},
        {"name": "删除权限", "code": "permission:delete", "module": "权限管理"},
        {"name": "查看日志", "code": "audit:read", "module": "审计日志"},
    ]
    permissions = [Permission(**data) for data in permission_data]
    db_session.add_all(permissions)
    await db_session.commit()
    return permissions


@pytest_asyncio.fixture
async def test_role(
    db_session: AsyncSession,
    test_permissions: list[Permission],
) -> Role:
    """Create an administrator role with all permissions."""
    role = Role(name="管理员", description="系统管理员", permissions=test_permissions)
    db_session.add(role)
    await db_session.commit()
    return role


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_role: Role) -> User:
    """Create an active non-superuser assigned to the administrator role."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("testpassword123"),
        nickname="测试用户",
        is_active=True,
        is_superuser=False,
        roles=[test_role],
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def superuser(db_session: AsyncSession) -> User:
    """Create an active superuser."""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("adminpassword123"),
        nickname="管理员",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def login_user(client: AsyncClient) -> LoginUser:
    """Return a helper that authenticates through the real login endpoint."""

    async def login(username: str, password: str) -> Headers:
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": password},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        token = payload["data"]["access_token"]
        assert isinstance(token, str)
        return {"Authorization": f"Bearer {token}"}

    return login


@pytest_asyncio.fixture
async def auth_headers(test_user: User, login_user: LoginUser) -> Headers:
    """Authenticate the regular test user and return an access-token header."""
    return await login_user(test_user.username, "testpassword123")


@pytest_asyncio.fixture
async def superuser_headers(superuser: User, login_user: LoginUser) -> Headers:
    """Authenticate the test superuser and return an access-token header."""
    return await login_user(superuser.username, "adminpassword123")
