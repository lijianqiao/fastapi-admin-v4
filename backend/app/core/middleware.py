"""Pure ASGI middleware for cross-cutting HTTP concerns."""

import logging

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_content

logger = logging.getLogger(__name__)


class UnhandledErrorMiddleware:
    """Render unexpected exceptions as the error envelope *inside* CORS.

    Starlette runs the ``Exception`` handler in ServerErrorMiddleware, which always
    wraps CORSMiddleware, so browsers could not read those 500 responses. Add this
    middleware before CORSMiddleware so it sits inside it.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_tracking_start(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_tracking_start)
        except Exception:
            if response_started:
                raise
            logger.exception("未捕获异常，路径: %s", scope.get("path", ""))
            response = JSONResponse(status_code=500, content=error_content(500, "服务器内部错误"))
            await response(scope, receive, send)
