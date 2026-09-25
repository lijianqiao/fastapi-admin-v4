"""FastAPI application factory and cross-cutting HTTP policies."""

import logging
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.core.deps import DbSession, collect_required_permissions
from app.core.errors import AppError, error_content, is_conflict_violation
from app.core.middleware import UnhandledErrorMiddleware
from app.core.request_context import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    install_request_id_log_field,
)


def configure_logging() -> None:
    """
    配置应用日志。
    根日志遵循 ``LOG_LEVEL``；SQLAlchemy 引擎/连接池默认仅输出 WARNING 及以上，
    需要 SQL 排障时设置 ``SQL_ECHO=true``。
    """
    install_request_id_log_field()
    logging.basicConfig(
        level=logging.getLevelName(settings.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s",
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
        """Convert uniqueness/reference races into 409; other violations are bugs."""
        if not is_conflict_violation(exc):
            logger.error("数据库约束错误，路径: %s", request.url.path, exc_info=exc)
            return JSONResponse(status_code=500, content=error_content(500, "服务器内部错误"))
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


def _iter_api_routes(routes: Sequence[object]) -> Iterator[APIRoute]:
    """展开路由，包含 FastAPI 0.141 惰性挂载、尚未摊平到 ``app.routes`` 的子路由。"""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue
        included = getattr(route, "original_router", None)
        nested = getattr(included, "routes", None)
        if isinstance(nested, Sequence):
            yield from _iter_api_routes(nested)


def annotate_route_permissions(app: FastAPI) -> None:
    """Expose each route's required permissions in OpenAPI as ``x-permissions``."""
    for route in _iter_api_routes(app.routes):
        codes = collect_required_permissions(route.dependant)
        if codes:
            route.openapi_extra = {
                **(route.openapi_extra or {}),
                "x-permissions": sorted(code.value for code in codes),
            }


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

    # 必须最先添加：位于 CORSMiddleware 内层，未捕获异常生成的 500 才会带上 CORS 头
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
    app.add_middleware(
        ProxyHeadersMiddleware,
        trusted_hosts=settings.TRUSTED_PROXY_CIDRS,
    )
    # 最后添加 = 最外层：被 TrustedHost 拒绝的请求和 500 响应同样带上请求 ID
    app.add_middleware(RequestIdMiddleware)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    annotate_route_permissions(app)

    @app.get("/health", tags=["系统"])
    async def health_check() -> dict[str, str]:
        """Return a process-level liveness signal without blocking a worker thread."""
        return {"status": "ok"}

    @app.get("/health/ready", tags=["系统"])
    async def readiness_check(db: DbSession) -> JSONResponse:
        """Report whether the database answers; for load-balancer readiness probes."""
        try:
            await db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("就绪检查失败：数据库不可用", exc_info=True)
            return JSONResponse(status_code=503, content=error_content(503, "数据库不可用"))
        return JSONResponse(content={"status": "ready"})

    register_exception_handlers(app)
    return app


app = create_app()
