"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: init_db.py
@DateTime: 2026-08-10
@Docs: 初始化超级管理员与系统权限种子数据
"""

import asyncio
import sys

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.permissions import PERMISSION_META
from app.core.security import hash_password_async
from app.models.user import User
from app.schemas.auth import UserRegister
from app.services.permission_sync import SyncResult, sync_system_permissions
from app.utils.audit import log_audit

BOOTSTRAP_ADVISORY_LOCK_ID = 0x4641535441504941


def _bootstrap_credentials() -> UserRegister:
    """
    读取并验证显式提供的初始化凭据。

    Returns:
        校验通过的注册凭据

    Raises:
        RuntimeError: 缺少配置或格式无效时
    """
    username = settings.INIT_SUPERUSER_USERNAME
    email = settings.INIT_SUPERUSER_EMAIL
    password_setting = settings.INIT_SUPERUSER_PASSWORD
    if username is None or email is None or password_setting is None:
        raise RuntimeError(
            "必须显式配置 INIT_SUPERUSER_USERNAME、INIT_SUPERUSER_EMAIL 和 INIT_SUPERUSER_PASSWORD"
        )

    try:
        return UserRegister.model_validate(
            {
                "username": username,
                "email": email,
                "password": password_setting.get_secret_value(),
            }
        )
    except ValidationError as exc:
        raise RuntimeError("初始化超级管理员配置格式无效") from exc


async def seed_permissions() -> SyncResult:
    """
    幂等同步系统权限（仅权限表，不创建角色或分配）。

    Returns:
        本次新增与修正的条数
    """
    async with AsyncSessionLocal() as db:
        try:
            if db.get_bind().dialect.name == "postgresql":
                await db.execute(select(func.pg_advisory_xact_lock(BOOTSTRAP_ADVISORY_LOCK_ID)))

            result = await sync_system_permissions(db)
            if result.created or result.updated:
                await log_audit(
                    db,
                    user_id=None,
                    action="bootstrap_permissions",
                    target="permissions",
                    detail=f"同步系统权限：新增 {result.created} 条，修正 {result.updated} 条",
                    ip="local",
                )
            await db.commit()
            return result
        except IntegrityError as exc:
            await db.rollback()
            raise RuntimeError("权限种子写入冲突；请重试或检查唯一约束") from exc
        except BaseException:
            await db.rollback()
            raise


async def _superuser_exists() -> bool:
    """判断系统中是否已有超级管理员。"""
    async with AsyncSessionLocal() as db:
        stmt = select(User.id).where(User.is_superuser.is_(True)).limit(1)
        return (await db.execute(stmt)).scalar_one_or_none() is not None


async def init_superuser() -> bool:
    """
    仅在用户名和邮箱均未被占用时创建新的超级管理员。

    Returns:
        是否新建了超级管理员

    Raises:
        RuntimeError: 配置无效或唯一约束冲突时
    """
    credentials = _bootstrap_credentials()
    async with AsyncSessionLocal() as db:
        try:
            if db.get_bind().dialect.name == "postgresql":
                await db.execute(select(func.pg_advisory_xact_lock(BOOTSTRAP_ADVISORY_LOCK_ID)))

            stmt = (
                select(User.id)
                .where(
                    or_(
                        User.is_superuser.is_(True),
                        User.username == credentials.username,
                        User.email == str(credentials.email),
                    )
                )
                .limit(1)
            )
            if (await db.execute(stmt)).scalar_one_or_none() is not None:
                return False

            user = User(
                username=credentials.username,
                email=str(credentials.email),
                hashed_password=await hash_password_async(credentials.password),
                nickname="超级管理员",
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            await db.flush()
            await log_audit(
                db,
                user_id=user.id,
                action="bootstrap_superuser",
                target=f"user:{user.id}",
                detail="创建首个超级管理员",
                ip="local",
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise RuntimeError("并发初始化或唯一约束冲突；超级管理员未创建") from exc
        except BaseException:
            await db.rollback()
            raise

    return True


async def bootstrap() -> None:
    """执行权限种子与超级管理员初始化。"""
    try:
        result = await seed_permissions()
        print(
            f"系统权限：新增 {result.created} 条，修正 {result.updated} 条"
            f"（共 {len(PERMISSION_META)} 条定义）"
        )

        has_init_credentials = (
            settings.INIT_SUPERUSER_USERNAME is not None
            and settings.INIT_SUPERUSER_EMAIL is not None
            and settings.INIT_SUPERUSER_PASSWORD is not None
        )
        if not has_init_credentials:
            if await _superuser_exists():
                print("未配置 INIT_SUPERUSER_*；已有超级管理员，跳过创建")
            else:
                raise RuntimeError(
                    "必须显式配置 INIT_SUPERUSER_USERNAME、INIT_SUPERUSER_EMAIL 和 INIT_SUPERUSER_PASSWORD"
                )
        elif await init_superuser():
            print("超级管理员创建成功（密码未输出）")
        else:
            print("超级管理员已存在或用户名/邮箱已占用；跳过创建")
    finally:
        await engine.dispose()


def main() -> None:
    """
    同步命令行入口。

    Windows 上使用 SelectorEventLoop，避免 psycopg 异步模式与 ProactorEventLoop 不兼容。
    """
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    try:
        asyncio.run(bootstrap(), loop_factory=loop_factory)
    except RuntimeError as exc:
        raise SystemExit(f"初始化失败：{exc}") from None


if __name__ == "__main__":
    main()
