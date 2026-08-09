"""Uvicorn 启动入口。

直接运行 ``python main.py`` 或 ``uv run python main.py`` 即可启动后端服务。
生产环境由进程管理器执行本入口；代理头统一由应用层可信代理配置解析。
"""

import asyncio
import sys

import uvicorn

from app.core.config import settings


def create_event_loop() -> asyncio.AbstractEventLoop:
    """Return a psycopg-compatible loop without deprecated loop policies."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def main() -> None:
    """启动 uvicorn ASGI 服务器。"""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL,
        loop="main:create_event_loop" if sys.platform == "win32" else "auto",
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
