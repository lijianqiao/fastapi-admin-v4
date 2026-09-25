"""Legacy bcrypt compatibility can be switched off once every hash is migrated."""

from typing import Any

import bcrypt
import pytest

from app.core import security
from app.core.config import settings
from app.core.security import hash_password, verify_and_update_password


def _legacy_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()


async def test_enabled_legacy_bcrypt_still_migrates() -> None:
    result = await verify_and_update_password("legacypassword1", _legacy_hash("legacypassword1"))

    assert result.valid
    assert result.updated_hash is not None
    assert result.updated_hash.startswith("$argon2")


async def test_disabled_legacy_bcrypt_rejects_bcrypt_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LEGACY_BCRYPT_ENABLED", False)

    result = await verify_and_update_password("legacypassword1", _legacy_hash("legacypassword1"))

    assert not result.valid


async def test_disabled_legacy_bcrypt_skips_bcrypt_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LEGACY_BCRYPT_ENABLED", False)
    calls: list[int] = []
    real_verify = security.BCRYPT_HASH.verify

    def counting_verify(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real_verify(*args, **kwargs)

    monkeypatch.setattr(security.BCRYPT_HASH, "verify", counting_verify)

    valid_login = await verify_and_update_password("goodpassword1", hash_password("goodpassword1"))
    unknown_user = await verify_and_update_password("whatever123", None)

    assert valid_login.valid
    assert not unknown_user.valid
    assert calls == []
