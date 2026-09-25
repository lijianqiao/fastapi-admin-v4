"""Per-request correlation ID shared by responses and log records."""

import logging
import re
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{8,64}")

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdMiddleware:
    """Accept a well-formed inbound X-Request-ID or mint one, and echo it back."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid4().hex
        token = request_id_var.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)


_record_factory_installed = False


def install_request_id_log_field() -> None:
    """Give every log record a ``request_id`` attribute (``-`` outside a request)."""
    global _record_factory_installed
    if _record_factory_installed:
        return
    previous_factory = logging.getLogRecordFactory()

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous_factory(*args, **kwargs)
        record.__dict__["request_id"] = request_id_var.get()
        return record

    logging.setLogRecordFactory(factory)
    _record_factory_installed = True
