"""登录限流器的容量与拒绝路径回归测试。"""

import pytest

from app.services.auth import LoginRateLimiter

pytestmark = pytest.mark.asyncio


async def test_throttled_attempts_do_not_grow_the_table() -> None:
    """被拒绝的尝试不得占用条目，否则单个 IP 就能把表打满。"""
    limiter = LoginRateLimiter(attempts=2, window_seconds=60)
    attacker_ip = "203.0.113.10"

    # 每次换一个用户名，只消耗 IP 维度的窗口（IP 上限为 attempts * 5）。
    index = 0
    while await limiter.hit(attacker_ip, f"user{index}") is None:
        index += 1
    size_after_throttling = len(limiter._entries)

    for probe in range(500):
        assert await limiter.hit(attacker_ip, f"probe{probe}") is not None

    assert len(limiter._entries) == size_after_throttling


async def test_full_table_still_admits_unseen_clients() -> None:
    """表满时必须淘汰最久未使用的窗口，而不是把所有新客户端拒之门外。"""
    limiter = LoginRateLimiter(attempts=2, window_seconds=60)

    for index in range(4000):
        await limiter.hit(f"198.51.100.{index % 256}", f"flood{index}")

    assert len(limiter._entries) <= LoginRateLimiter._MAX_ENTRIES
    assert await limiter.hit("192.0.2.77", "legitimate-user") is None


async def test_successful_login_clears_account_and_pair_windows() -> None:
    """登录成功后释放账户与 IP+账户窗口，避免正常用户被自己的历史拖累。"""
    limiter = LoginRateLimiter(attempts=2, window_seconds=60)

    assert await limiter.hit("192.0.2.5", "alice") is None
    assert await limiter.hit("192.0.2.5", "alice") is None
    assert await limiter.hit("192.0.2.5", "alice") is not None

    await limiter.clear("192.0.2.5", "alice")

    assert await limiter.hit("192.0.2.5", "alice") is None
