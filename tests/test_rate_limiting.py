"""
Tests for rate limiting: global, per-key, and per-IP rate limits.
"""

import os
import sys
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))

from server import (
    check_global_rate_limit,
    check_per_key_rate_limit,
    check_ip_rate_limit,
    global_rate_limit_store,
    rate_limit_store,
    ip_rate_limit_store,
)


def _clear_stores():
    # Other test modules reload `server`, which replaces these module-level
    # stores, so always clear the live ones rather than the names imported above.
    live = sys.modules['server']
    live.global_rate_limit_store.clear()
    live.rate_limit_store.clear()
    live.ip_rate_limit_store.clear()


@pytest.fixture(autouse=True)
def clear_rate_limit_stores():
    """Clear all rate limit stores before each test."""
    _clear_stores()
    yield
    _clear_stores()


class TestGlobalRateLimit:
    """Test global rate limiting (shared across all keys)."""

    def test_allows_within_limit(self):
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 10,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 1000,
            'ip_rate_limit_window': 60,
        }):
            allowed, remaining, limit, window = check_global_rate_limit()
            assert allowed is True
            assert remaining == 9  # limit(10) - count(0) - 1 = 9, then append
            assert limit == 10
            assert window == 60

    def test_blocks_at_limit(self):
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 3,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 1000,
            'ip_rate_limit_window': 60,
        }):
            # Use up the limit
            check_global_rate_limit()  # 1
            check_global_rate_limit()  # 2
            check_global_rate_limit()  # 3

            # Should be blocked now
            allowed, remaining, limit, window = check_global_rate_limit()
            assert allowed is False
            assert remaining == 0

    def test_cleans_old_entries(self):
        # The global store is reassigned in the function, so we need to test
        # by calling through the function itself
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 3,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 1000,
            'ip_rate_limit_window': 60,
        }):
            # Use up 2 of 3
            check_global_rate_limit()
            check_global_rate_limit()

            # Manually age the entries by modifying the store
            import server
            server.global_rate_limit_store[:] = [time.time() - 120, time.time() - 120]

            # Should be allowed again since old entries get cleaned
            allowed, remaining, limit, window = check_global_rate_limit()
            assert allowed is True


class TestPerKeyRateLimit:
    """Test per-key rate limiting."""

    def test_no_limit_set_uses_default_per_key_limit(self):
        """Keys without their own limit get the default per-key limit, so one
        key cannot use up the shared global ceiling (audit hardening)."""
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 100,
            'rate_limit_window': 60,
            'key_rate_limit_requests': 3,
            'ip_rate_limit_requests': 1000,
            'ip_rate_limit_window': 60,
        }):
            results = [check_per_key_rate_limit("key1", None) for _ in range(4)]
            assert [allowed for allowed, _, _ in results] == [True, True, True, False]
            assert results[0][2] == 3
            # Another key is unaffected
            assert check_per_key_rate_limit("key2", None)[0] is True

    def test_idle_entries_are_swept(self):
        """Per-IP entries for clients that went away are deleted, so spoofed or
        rotating addresses cannot grow the store forever."""
        live = sys.modules['server']
        old = time.time() - 3600
        for i in range(100):
            live.ip_rate_limit_store[f"10.0.0.{i}"] = [old]
        live._last_sweep['ip'] = 0.0
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 100, 'rate_limit_window': 60,
            'key_rate_limit_requests': 60,
            'ip_rate_limit_requests': 1000, 'ip_rate_limit_window': 60,
        }):
            check_ip_rate_limit("203.0.113.9")
        assert list(live.ip_rate_limit_store) == ["203.0.113.9"]

    def test_allows_within_limit(self):
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 100,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 1000,
            'ip_rate_limit_window': 60,
        }):
            allowed, remaining, limit = check_per_key_rate_limit("key1", 5)
            assert allowed is True
            assert remaining == 4  # limit(5) - count(0) - 1 = 4
            assert limit == 5

    def test_blocks_at_limit(self):
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 100,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 1000,
            'ip_rate_limit_window': 60,
        }):
            for _ in range(5):
                check_per_key_rate_limit("key1", 5)

            allowed, remaining, limit = check_per_key_rate_limit("key1", 5)
            assert allowed is False
            assert remaining == 0

    def test_separate_key_stores(self):
        """Rate limits should be independent per key."""
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 100,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 1000,
            'ip_rate_limit_window': 60,
        }):
            # Exhaust key1
            for _ in range(3):
                check_per_key_rate_limit("key1", 3)
            blocked, _, _ = check_per_key_rate_limit("key1", 3)
            assert blocked is False

            # key2 should still be allowed
            allowed, _, _ = check_per_key_rate_limit("key2", 3)
            assert allowed is True


class TestIPRateLimit:
    """Test IP-based rate limiting."""

    def test_allows_within_limit(self):
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 100,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 10,
            'ip_rate_limit_window': 60,
        }):
            allowed, remaining, limit, window = check_ip_rate_limit("192.168.1.1")
            assert allowed is True
            assert limit == 10

    def test_blocks_at_limit(self):
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 100,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 3,
            'ip_rate_limit_window': 60,
        }):
            for _ in range(3):
                check_ip_rate_limit("192.168.1.1")

            allowed, remaining, limit, window = check_ip_rate_limit("192.168.1.1")
            assert allowed is False
            assert remaining == 0

    def test_separate_ip_stores(self):
        """Different IPs should have separate rate limit buckets."""
        with patch('server.get_rate_limit_settings', return_value={
            'rate_limit_requests': 100,
            'rate_limit_window': 60,
            'ip_rate_limit_requests': 2,
            'ip_rate_limit_window': 60,
        }):
            # Exhaust IP 1
            check_ip_rate_limit("10.0.0.1")
            check_ip_rate_limit("10.0.0.1")
            blocked, _, _, _ = check_ip_rate_limit("10.0.0.1")
            assert blocked is False

            # IP 2 should still be allowed
            allowed, _, _, _ = check_ip_rate_limit("10.0.0.2")
            assert allowed is True
