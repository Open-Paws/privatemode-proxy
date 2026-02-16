"""
Tests for admin UI: authentication, session management, key CRUD, rate limit settings.
"""

import json
import os
import sys
import time
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))

from admin import (
    create_session,
    validate_session,
    delete_session,
    _sessions,
    check_login_rate_limit,
    _login_attempts,
    generate_csrf_token,
    validate_csrf_token,
    _csrf_tokens,
    load_keys,
    save_keys,
    load_settings,
    save_settings,
    get_key_status,
    format_timestamp,
    update_key_rate_limit,
)
from tests.helpers import make_keys_file


@pytest.fixture(autouse=True)
def clear_admin_state():
    """Clear session and rate limit state between tests."""
    _sessions.clear()
    _login_attempts.clear()
    _csrf_tokens.clear()
    yield
    _sessions.clear()
    _login_attempts.clear()
    _csrf_tokens.clear()


class TestSessionManagement:
    """Test admin session create/validate/delete."""

    def test_create_and_validate(self):
        token = create_session("127.0.0.1")
        assert token is not None
        assert len(token) > 20
        assert validate_session(token, "127.0.0.1") is True

    def test_validate_wrong_ip(self):
        token = create_session("127.0.0.1")
        assert validate_session(token, "10.0.0.1") is False

    def test_validate_nonexistent(self):
        assert validate_session("nonexistent_token", "127.0.0.1") is False

    def test_validate_empty(self):
        assert validate_session("", "127.0.0.1") is False
        assert validate_session(None, "127.0.0.1") is False

    def test_delete_session(self):
        token = create_session("127.0.0.1")
        assert validate_session(token, "127.0.0.1") is True
        delete_session(token)
        assert validate_session(token, "127.0.0.1") is False

    def test_delete_nonexistent(self):
        # Should not raise
        delete_session("nonexistent")

    def test_expired_session(self):
        token = create_session("127.0.0.1")
        # Manually expire the session
        created_at, ip = _sessions[token]
        _sessions[token] = (created_at - 90000, ip)  # > SESSION_TTL (86400)
        assert validate_session(token, "127.0.0.1") is False


class TestLoginRateLimit:
    """Test admin login rate limiting."""

    def test_allows_initial_attempts(self):
        assert check_login_rate_limit("127.0.0.1") is True

    def test_blocks_after_max_attempts(self):
        ip = "10.0.0.1"
        for _ in range(5):
            check_login_rate_limit(ip, record_attempt=True)

        assert check_login_rate_limit(ip) is False

    def test_separate_ips(self):
        ip1 = "10.0.0.1"
        ip2 = "10.0.0.2"

        for _ in range(5):
            check_login_rate_limit(ip1, record_attempt=True)

        assert check_login_rate_limit(ip1) is False
        assert check_login_rate_limit(ip2) is True

    def test_only_records_when_told(self):
        ip = "10.0.0.3"
        # Check without recording - should not count toward limit
        for _ in range(10):
            check_login_rate_limit(ip, record_attempt=False)
        assert check_login_rate_limit(ip) is True


class TestCSRFTokens:
    """Test CSRF token generation and validation."""

    def test_generate_and_validate(self):
        token = generate_csrf_token()
        assert validate_csrf_token(token) is True

    def test_token_consumed_on_use(self):
        token = generate_csrf_token()
        assert validate_csrf_token(token) is True
        # Second use should fail (consumed)
        assert validate_csrf_token(token) is False

    def test_invalid_token(self):
        assert validate_csrf_token("nonexistent") is False

    def test_empty_token(self):
        assert validate_csrf_token("") is False
        assert validate_csrf_token(None) is False

    def test_expired_token(self):
        token = generate_csrf_token()
        # Manually expire it
        _csrf_tokens[token] = time.time() - 7200  # 2 hours ago (TTL is 1 hour)
        assert validate_csrf_token(token) is False


class TestKeysCRUD:
    """Test loading and saving API keys."""

    def test_load_keys(self, tmp_path):
        keys_file = make_keys_file(tmp_path)
        with patch('admin.KEYS_FILE', keys_file):
            data = load_keys()
            assert 'keys' in data
            assert len(data['keys']) == 4

    def test_load_missing_file(self, tmp_path):
        with patch('admin.KEYS_FILE', os.path.join(str(tmp_path), 'nope.json')):
            data = load_keys()
            assert data == {"keys": []}

    def test_save_and_reload(self, tmp_path):
        keys_file = os.path.join(str(tmp_path), 'keys.json')
        with patch('admin.KEYS_FILE', keys_file):
            save_keys({"keys": [{"key_id": "x", "enabled": True}]})
            data = load_keys()
            assert len(data['keys']) == 1
            assert data['keys'][0]['key_id'] == 'x'

    def test_update_key_rate_limit(self, tmp_path):
        keys_file = make_keys_file(tmp_path)
        with patch('admin.KEYS_FILE', keys_file):
            result = update_key_rate_limit("test_key_1", 50)
            assert result is True

            # Verify it was saved
            data = load_keys()
            key = next(k for k in data['keys'] if k['key_id'] == 'test_key_1')
            assert key['rate_limit'] == 50

    def test_update_key_rate_limit_clear(self, tmp_path):
        keys_file = make_keys_file(tmp_path)
        with patch('admin.KEYS_FILE', keys_file):
            # key_2 has rate_limit=5
            update_key_rate_limit("test_key_2", None)

            data = load_keys()
            key = next(k for k in data['keys'] if k['key_id'] == 'test_key_2')
            assert 'rate_limit' not in key

    def test_update_nonexistent_key(self, tmp_path):
        keys_file = make_keys_file(tmp_path)
        with patch('admin.KEYS_FILE', keys_file):
            result = update_key_rate_limit("nonexistent", 10)
            assert result is False


class TestSettings:
    """Test settings load/save."""

    def test_load_defaults(self, tmp_path):
        with patch('admin.SETTINGS_FILE', os.path.join(str(tmp_path), 'nope.json')):
            settings = load_settings()
            assert 'rate_limit_requests' in settings
            assert 'ip_rate_limit_requests' in settings

    def test_save_and_load(self, tmp_path):
        settings_file = os.path.join(str(tmp_path), 'settings.json')
        with patch('admin.SETTINGS_FILE', settings_file):
            save_settings({'rate_limit_requests': 200, 'custom': 'value'})
            settings = load_settings()
            assert settings['rate_limit_requests'] == 200
            assert settings['custom'] == 'value'
            # Defaults should still be present
            assert 'ip_rate_limit_requests' in settings


class TestHelpers:
    """Test admin helper functions."""

    def test_get_key_status_active(self):
        key = {'enabled': True}
        status, css = get_key_status(key)
        assert status == "Active"
        assert css == "status-active"

    def test_get_key_status_revoked(self):
        key = {'enabled': False}
        status, css = get_key_status(key)
        assert status == "Revoked"
        assert css == "status-revoked"

    def test_get_key_status_expired(self):
        key = {'enabled': True, 'expires_at': time.time() - 3600}
        status, css = get_key_status(key)
        assert status == "Expired"
        assert css == "status-expired"

    def test_format_timestamp_none(self):
        assert format_timestamp(None) == "Never"

    def test_format_timestamp_valid(self):
        ts = 1700000000.0  # 2023-11-14
        result = format_timestamp(ts)
        assert "2023" in result
