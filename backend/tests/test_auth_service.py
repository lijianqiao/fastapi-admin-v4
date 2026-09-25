"""Authentication use case: the KDF must run without an open transaction."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import PasswordVerification
from app.models.user import User
from app.services import auth as auth_service


async def test_authenticate_releases_transaction_before_kdf(
    db_session: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[bool] = []
    real_verify = auth_service.verify_and_update_password

    async def spy(password: str, hashed: str | None) -> PasswordVerification:
        observed.append(db_session.in_transaction())
        return await real_verify(password, hashed)

    monkeypatch.setattr(auth_service, "verify_and_update_password", spy)

    user = await auth_service.authenticate_user(db_session, "testuser", "testpassword123")

    assert user is not None
    assert observed == [False]
