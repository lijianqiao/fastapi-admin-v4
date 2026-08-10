"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: init_db.py
@DateTime: 2026-08-10
@Docs: 初始化超级管理员与系统权限种子数据
"""

import asyncio
import sys
from typing import TypedDict

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password_async
from app.models.permission import Permission
from app.models.user import User
from app.schemas.auth import UserRegister
from app.utils.audit import log_audit

BOOTSTRAP_ADVISORY_LOCK_ID = 0x4641535441504941


class SeedPermission(TypedDict):
    """权限种子条目。"""

    name: str
    code: str
    module: str
    description: str


# 与后端 require_permission / 前端 PERMISSIONS / 测试种子保持一致；不创建角色或分配关系
SEED_PERMISSIONS: tuple[SeedPermission, ...] = (
    {
        "name": "查看用户",
        "code": "user:read",
        "module": "用户管理",
        "description": "查看用户列表与详情",
    },
    {
        "name": "创建用户",
        "code": "user:create",
        "module": "用户管理",
        "description": "创建新用户",
    },
    {
        "name": "更新用户",
        "code": "user:update",
        "module": "用户管理",
        "description": "更新用户资料与状态",
    },
    {
        "name": "删除用户",
        "code": "user:delete",
        "module": "用户管理",
        "description": "软删除用户，并管理用户回收站（恢复/永久删除）",
    },
    {
        "name": "分配角色",
        "code": "user:assign",
        "module": "用户管理",
        "description": "为用户分配角色",
    },
    {
        "name": "重置密码",
        "code": "user:reset_password",
        "module": "用户管理",
        "description": "重置其他用户密码",
    },
    {
        "name": "查看角色",
        "code": "role:read",
        "module": "角色管理",
        "description": "查看角色列表与详情",
    },
    {
        "name": "创建角色",
        "code": "role:create",
        "module": "角色管理",
        "description": "创建新角色",
    },
    {
        "name": "更新角色",
        "code": "role:update",
        "module": "角色管理",
        "description": "更新角色信息",
    },
    {
        "name": "删除角色",
        "code": "role:delete",
        "module": "角色管理",
        "description": "软删除角色，并管理角色回收站（恢复/永久删除）",
    },
    {
        "name": "分配权限",
        "code": "role:assign",
        "module": "角色管理",
        "description": "为角色分配权限",
    },
    {
        "name": "查看权限",
        "code": "permission:read",
        "module": "权限管理",
        "description": "查看权限列表",
    },
    {
        "name": "创建权限",
        "code": "permission:create",
        "module": "权限管理",
        "description": "创建新权限",
    },
    {
        "name": "更新权限",
        "code": "permission:update",
        "module": "权限管理",
        "description": "更新权限信息",
    },
    {
        "name": "删除权限",
        "code": "permission:delete",
        "module": "权限管理",
        "description": "软删除权限，并管理权限回收站（恢复/永久删除）",
    },
    {
        "name": "查看日志",
        "code": "audit:read",
        "module": "审计日志",
        "description": "查看审计日志",
    },
)


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


async def seed_permissions() -> int:
    """
    幂等写入系统权限种子（仅权限表，不创建角色或分配）。

    Returns:
        新插入的权限条数
    """
    codes = [item["code"] for item in SEED_PERMISSIONS]
    async with AsyncSessionLocal() as db:
        try:
            if db.get_bind().dialect.name == "postgresql":
                await db.execute(select(func.pg_advisory_xact_lock(BOOTSTRAP_ADVISORY_LOCK_ID)))

            result = await db.execute(select(Permission.code).where(Permission.code.in_(codes)))
            existing_codes = set(result.scalars().all())
            created = 0
            for item in SEED_PERMISSIONS:
                if item["code"] in existing_codes:
                    continue
                db.add(
                    Permission(
                        name=item["name"],
                        code=item["code"],
                        module=item["module"],
                        description=item["description"],
                    )
                )
                created += 1

            if created:
                await log_audit(
                    db,
                    user_id=None,
                    action="bootstrap_permissions",
                    target="permissions",
                    detail=f"种子写入 {created} 条权限",
                    ip="local",
                )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise RuntimeError("权限种子写入冲突；请重试或检查唯一约束") from exc
        except BaseException:
            await db.rollback()
            raise

    return created


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
        created_permissions = await seed_permissions()
        if created_permissions:
            print(f"权限种子：新增 {created_permissions} 条（共 {len(SEED_PERMISSIONS)} 条定义）")
        else:
            print(f"权限种子：已齐全，跳过写入（共 {len(SEED_PERMISSIONS)} 条定义）")

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
