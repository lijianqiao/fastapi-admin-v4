"""Central refresh-cookie policy."""

from fastapi import Response

from app.core.config import settings

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = f"{settings.API_V1_PREFIX}/auth"
REFRESH_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def set_refresh_cookie(response: Response, token: str) -> None:
    """Set a restricted refresh-token cookie."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Expire the cookie with the same attributes used when it was issued."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=settings.COOKIE_SECURE,
        httponly=True,
        samesite="strict",
    )
