"""FastAPI application factory and cross-cutting HTTP policies."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.errors import AppError, error_content


def configure_logging() -> None:
    """
    配置应用日志。
    根日志遵循 ``LOG_LEVEL``；SQLAlchemy 引擎/连接池默认仅输出 WARNING 及以上，
    需要 SQL 排障时设置 ``SQL_ECHO=true``。
    """
    logging.basicConfig(
        level=logging.getLevelName(settings.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    sql_level = logging.INFO if settings.SQL_ECHO else logging.WARNING
    logging.getLogger("sqlalchemy.engine").setLevel(sql_level)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Release pooled database connections during graceful shutdown."""
    yield
    await engine.dispose()


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the shared error envelope to every failure path."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """Preserve the HTTP status while applying the shared error envelope."""
        detail = exc.detail
        message = detail if isinstance(detail, str) else "请求失败"
        data = None if isinstance(detail, str) else jsonable_encoder(detail)
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=error_content(exc.status_code, message, data),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Return machine-readable validation details with HTTP 422."""
        errors = [
            {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            headers={"Cache-Control": "no-store"},
            content=error_content(422, "请求参数校验失败", {"errors": jsonable_encoder(errors)}),
        )

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(
        request: Request,
        exc: IntegrityError,
    ) -> JSONResponse:
        """Convert database constraint races into a safe conflict response."""
        logger.info("数据库约束冲突，路径: %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=409,
            content=error_content(409, "资源已存在或仍被其他数据引用"),
        )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        """Render every expected domain failure with its declared status."""
        if exc.status_code >= 500:
            logger.warning("服务暂不可用: %s", exc.message, exc_info=exc)
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=error_content(exc.status_code, exc.message, exc.data),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Hide implementation details from unexpected server errors."""
        logger.error("未捕获异常，路径: %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_content(500, "服务器内部错误"),
        )


def create_app() -> FastAPI:
    """Create a configured FastAPI application."""
    production = settings.ENVIRONMENT == "production"
    app = FastAPI(
        title="FastAPI 权限管理系统",
        description="基于 RBAC 模型的权限管理系统 API",
        version="1.0.0",
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
    app.add_middleware(
        ProxyHeadersMiddleware,
        trusted_hosts=settings.TRUSTED_PROXY_CIDRS,
    )
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/health", tags=["系统"])
    async def health_check() -> dict[str, str]:
        """Return a process-level liveness signal without blocking a worker thread."""
        return {"status": "ok"}

    register_exception_handlers(app)
    return app


app = create_app()
