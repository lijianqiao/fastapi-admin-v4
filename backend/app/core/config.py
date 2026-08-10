"""应用配置。

配置从稳定的 ``backend/.env`` 路径和环境变量加载，并在应用导入时完成校验。
生产环境对密钥、Cookie 和调试选项采用 fail-fast 策略。
"""

from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from secrets import token_urlsafe
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_ROOT / ".env"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://fastapi_admin_app:password@localhost:5432/fastapi_admin"
)

type Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """类型安全的应用配置。"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="forbid",
    )

    # 数据库
    DATABASE_URL: str = DEFAULT_DATABASE_URL
    MIGRATION_DATABASE_URL: SecretStr | None = None
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0, le=100)

    # JWT / 会话
    SECRET_KEY: SecretStr | None = None
    ALGORITHM: Literal["HS256"] = "HS256"
    JWT_ISSUER: str = "fastapi-admin"
    JWT_AUDIENCE: str = "fastapi-admin-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=1, le=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)
    REFRESH_SESSION_REPLAY_GRACE_DAYS: int = Field(default=1, ge=0, le=7)
    REFRESH_SESSION_HISTORY_RETENTION_DAYS: int = Field(default=30, ge=7, le=365)
    REFRESH_SESSION_CLEANUP_BATCH_SIZE: int = Field(default=1000, ge=100, le=10_000)

    # 登录保护（进程内兜底；生产仍应在网关配置共享限流）
    LOGIN_RATE_LIMIT_ATTEMPTS: int = Field(default=5, ge=1, le=100)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
    REGISTRATION_RATE_LIMIT_ATTEMPTS: int = Field(default=5, ge=1, le=100)
    PASSWORD_HASH_MAX_CONCURRENCY: int = Field(default=4, ge=1, le=32)
    PASSWORD_HASH_QUEUE_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=30)

    # CORS / Cookie / 代理
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,test"
    COOKIE_SECURE: bool = False
    TRUSTED_PROXY_CIDRS: str = "127.0.0.1/32,::1/128"

    # 应用
    ENVIRONMENT: Environment = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = Field(default=8000, ge=1, le=65535)
    LOG_LEVEL: Literal["critical", "error", "warning", "info", "debug"] = "info"
    # 仅在排查 SQL 时开启；默认关闭，避免控制台被引擎日志淹没
    SQL_ECHO: bool = False
    API_V1_PREFIX: str = "/api/v1"
    REGISTRATION_ENABLED: bool = False

    # 初始化超级管理员；仅 init_db.py 使用，不提供可工作的默认密码
    INIT_SUPERUSER_USERNAME: str | None = None
    INIT_SUPERUSER_EMAIL: str | None = None
    INIT_SUPERUSER_PASSWORD: SecretStr | None = None

    @field_validator("TRUSTED_PROXY_CIDRS")
    @classmethod
    def validate_trusted_proxy_cidrs(cls, value: str) -> str:
        """在启动时验证可信代理网段。"""
        for item in value.split(","):
            candidate = item.strip()
            if candidate:
                ip_network(candidate, strict=False)
        return value

    @field_validator("MIGRATION_DATABASE_URL")
    @classmethod
    def validate_migration_database_url(
        cls,
        value: SecretStr | None,
    ) -> SecretStr | None:
        """Reject unusable migration URLs without exposing their credentials."""
        if value is None:
            return None
        try:
            database_url = make_url(value.get_secret_value())
        except ArgumentError as exc:
            raise ValueError("MIGRATION_DATABASE_URL 格式无效") from exc
        if database_url.get_backend_name() != "postgresql":
            raise ValueError("数据库迁移仅支持 PostgreSQL")
        return value

    @model_validator(mode="after")
    def validate_security_settings(self) -> Self:
        """校验跨字段安全约束，并为本地开发生成临时密钥。"""
        if self.SECRET_KEY is None:
            if self.ENVIRONMENT == "production":
                raise ValueError("生产环境必须显式配置 SECRET_KEY")
            self.SECRET_KEY = SecretStr(token_urlsafe(48))

        if len(self.SECRET_KEY.get_secret_value()) < 32:
            raise ValueError("SECRET_KEY 至少需要 32 个字符")

        if self.ENVIRONMENT == "production":
            try:
                database_url = make_url(self.DATABASE_URL)
            except ArgumentError as exc:
                raise ValueError("DATABASE_URL 格式无效") from exc
            password = database_url.password or ""
            if database_url.get_backend_name() != "postgresql":
                raise ValueError("生产环境仅支持 PostgreSQL")
            if password.casefold() in {"", "change-me", "changeme", "password", "postgres"}:
                raise ValueError("生产环境必须配置非占位数据库密码")
            if self.MIGRATION_DATABASE_URL is not None:
                migration_url = make_url(self.MIGRATION_DATABASE_URL.get_secret_value())
                migration_password = migration_url.password or ""
                if migration_password.casefold() in {
                    "",
                    "change-me",
                    "changeme",
                    "password",
                    "postgres",
                }:
                    raise ValueError("生产迁移账号必须配置非占位数据库密码")
            if self.DEBUG:
                raise ValueError("生产环境禁止启用 DEBUG")
            if not self.COOKIE_SECURE:
                raise ValueError("生产环境必须启用 COOKIE_SECURE")
            if "*" in self.cors_origins_list:
                raise ValueError("携带凭据的生产 CORS 配置禁止使用通配符")
            if any(
                urlsplit(origin).scheme != "https"
                or urlsplit(origin).hostname in {None, "localhost", "127.0.0.1", "::1"}
                for origin in self.cors_origins_list
            ):
                raise ValueError("生产环境 CORS 来源必须是显式的 HTTPS 公网域名")
            if not self.allowed_hosts_list or any("*" in host for host in self.allowed_hosts_list):
                raise ValueError("生产环境必须显式配置 ALLOWED_HOSTS，且禁止通配符")
            if any(
                host.casefold() in {"localhost", "127.0.0.1", "::1", "test"}
                for host in self.allowed_hosts_list
            ):
                raise ValueError("生产环境 ALLOWED_HOSTS 不能使用开发默认主机")
            if self.INIT_SUPERUSER_PASSWORD is not None:
                password = self.INIT_SUPERUSER_PASSWORD.get_secret_value()
                if len(password) < 12:
                    raise ValueError("生产环境初始超级管理员密码至少需要 12 个字符")

        return self

    @property
    def secret_key(self) -> str:
        """返回仅供签名组件使用的密钥明文。"""
        if self.SECRET_KEY is None:  # pragma: no cover - 已由模型校验保证
            raise RuntimeError("SECRET_KEY 未初始化")
        return self.SECRET_KEY.get_secret_value()

    @property
    def migration_database_url(self) -> str:
        """Return the privileged URL only to the one-off migration process.

        Development may reuse the application connection for convenience. A
        production Alembic run must inject a distinct migration role so the
        long-running web process can keep a DML-only credential.
        """
        if self.MIGRATION_DATABASE_URL is None:
            if self.ENVIRONMENT == "production":
                raise RuntimeError("生产数据库迁移必须显式配置 MIGRATION_DATABASE_URL")
            return self.DATABASE_URL

        migration_url = self.MIGRATION_DATABASE_URL.get_secret_value()
        if self.ENVIRONMENT == "production":
            runtime_username = make_url(self.DATABASE_URL).username
            migration_username = make_url(migration_url).username
            if migration_username == runtime_username:
                raise RuntimeError("生产迁移账号必须与运行时数据库账号分离")
        return migration_url

    @property
    def cors_origins_list(self) -> list[str]:
        """将逗号分隔的 CORS 来源转换为列表。"""
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Return the validated host-header allowlist."""
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]


@lru_cache
def get_settings() -> Settings:
    """获取进程内配置单例。"""
    return Settings()


settings = get_settings()
