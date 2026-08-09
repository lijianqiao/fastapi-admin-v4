"""安全创建首个超级管理员。

运行前必须先执行 Alembic 迁移，并通过环境变量显式提供三个
``INIT_SUPERUSER_*`` 配置。脚本不会建表、提升或覆盖已有账户。
"""

import asyncio

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password_async
from app.models.user import User
from app.schemas.auth import UserRegister
from app.utils.audit import log_audit

BOOTSTRAP_ADVISORY_LOCK_ID = 0x4641535441504941


def _bootstrap_credentials() -> UserRegister:
    """读取并验证显式提供的初始化凭据。"""
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


async def init_superuser() -> None:
    """仅在用户名和邮箱均未被占用时创建新的超级管理员。"""
    credentials = _bootstrap_credentials()
    async with AsyncSessionLocal() as db:
        try:
            # The bootstrap is a database-wide singleton operation. PostgreSQL's
            # transaction advisory lock also protects the completely empty-table
            # case where SELECT FOR UPDATE has no row to lock.
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
                raise RuntimeError("系统已存在超级管理员，或用户名/邮箱已占用；未修改任何账户")

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

    print("超级管理员创建成功（密码未输出）")


def main() -> None:
    """同步命令行入口。"""
    try:
        asyncio.run(init_superuser())
    except RuntimeError as exc:
        raise SystemExit(f"初始化失败：{exc}") from None


if __name__ == "__main__":
    main()
