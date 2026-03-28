"""
Tests for authentication: API key extraction, validation, and middleware behavior.
"""

import hashlib
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))

from tests.helpers import (
    TEST_API_KEY, TEST_API_KEY_2, EXPIRED_API_KEY, DISABLED_API_KEY,
    make_keys_file,
)


class TestExtractApiKey:
    """Test API key extraction from request headers."""

    def test_bearer_token(self):
        from server import extract_api_key
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers = {'Authorization': f'Bearer {TEST_API_KEY}'}
        assert extract_api_key(request) == TEST_API_KEY

    def test_x_api_key_header(self):
        from server import extract_api_key
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda key, default='': (
            '' if key == 'Authorization' else
            TEST_API_KEY if key == 'X-API-Key' else default
        ))
        assert extract_api_key(request) == TEST_API_KEY

    def test_missing_key(self):
        from server import extract_api_key
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda key, default='': '')
        assert extract_api_key(request) is None

    def test_bearer_prefix_only(self):
        from server import extract_api_key
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = lambda key, default='': 'Bearer ' if key == 'Authorization' else None
        # "Bearer " with empty key returns empty string
        result = extract_api_key(request)
        assert result == ''

    def test_non_bearer_auth_header(self):
        from server import extract_api_key
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = lambda key, default='': (
            'Basic dXNlcjpwYXNz' if key == 'Authorization' else None
        )
        # Basic auth should not be extracted as API key
        assert extract_api_key(request) is None


class TestKeyManager:
    """Test KeyManager key validation and lifecycle."""

    def test_validate_valid_key(self, tmp_path):
        from key_manager import KeyManager

        keys_file = make_keys_file(tmp_path)
        km = KeyManager(keys_file)

        valid, key_obj = km.validate_key(TEST_API_KEY)
        assert valid is True
        assert key_obj is not None
        assert key_obj.key_id == "test_key_1"

    def test_validate_invalid_key(self, tmp_path):
        from key_manager import KeyManager

        keys_file = make_keys_file(tmp_path)
        km = KeyManager(keys_file)

        valid, key_obj = km.validate_key("pm_nonexistent_key")
        assert valid is False
        assert key_obj is None

    def test_validate_expired_key(self, tmp_path):
        from key_manager import KeyManager

        keys_file = make_keys_file(tmp_path)
        km = KeyManager(keys_file)

        valid, key_obj = km.validate_key(EXPIRED_API_KEY)
        assert valid is False

    def test_validate_disabled_key(self, tmp_path):
        from key_manager import KeyManager

        keys_file = make_keys_file(tmp_path)
        km = KeyManager(keys_file)

        valid, key_obj = km.validate_key(DISABLED_API_KEY)
        assert valid is False

    def test_key_with_rate_limit(self, tmp_path):
        from key_manager import KeyManager

        keys_file = make_keys_file(tmp_path)
        km = KeyManager(keys_file)

        valid, key_obj = km.validate_key(TEST_API_KEY_2)
        assert valid is True
        assert key_obj.rate_limit == 5

    def test_get_key_info(self, tmp_path):
        from key_manager import KeyManager

        keys_file = make_keys_file(tmp_path)
        km = KeyManager(keys_file)

        info = km.get_key_info(TEST_API_KEY)
        assert info is not None
        assert info['key_id'] == "test_key_1"
        assert info['description'] == "Test key 1"
        assert 'key_hash' not in info  # Shouldn't leak the hash

    def test_get_key_info_invalid(self, tmp_path):
        from key_manager import KeyManager

        keys_file = make_keys_file(tmp_path)
        km = KeyManager(keys_file)

        info = km.get_key_info("pm_nonexistent")
        assert info is None

    def test_hot_reload(self, tmp_path):
        import json
        from key_manager import KeyManager

        keys_file = make_keys_file(tmp_path)
        km = KeyManager(keys_file)

        # Verify initial key works
        valid, _ = km.validate_key(TEST_API_KEY)
        assert valid is True

        # Add a new key to the file
        new_key = "pm_hot_reload_key"
        new_hash = hashlib.sha256(new_key.encode()).hexdigest()
        data = {
            "keys": [
                {
                    "key_id": "hot_reload_key",
                    "key_hash": new_hash,
                    "created_at": time.time(),
                    "enabled": True,
                }
            ]
        }
        # Ensure file modification time changes
        time.sleep(0.1)
        with open(keys_file, "w") as f:
            json.dump(data, f)

        # Trigger reload
        km.reload_if_changed()

        # New key should work, old key should not
        valid, _ = km.validate_key(new_key)
        assert valid is True
        valid, _ = km.validate_key(TEST_API_KEY)
        assert valid is False

    def test_missing_keys_file(self, tmp_path):
        from key_manager import KeyManager

        km = KeyManager(os.path.join(str(tmp_path), "nonexistent.json"))
        valid, _ = km.validate_key(TEST_API_KEY)
        assert valid is False

    def test_env_keys_loading(self, tmp_path):
        from key_manager import KeyManager

        env_key = "pm_env_loaded_key"
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("API_KEYS", env_key)
            km = KeyManager(os.path.join(str(tmp_path), "nonexistent.json"))
            valid, key_obj = km.validate_key(env_key)
            assert valid is True
            assert key_obj.key_id == "env_key_0"


class TestKeyGeneration:
    """Test API key generation utilities."""

    def test_generate_key_format(self):
        from key_manager import generate_api_key

        key = generate_api_key()
        assert key.startswith("pm_")
        assert len(key) > 10

    def test_generate_key_custom_prefix(self):
        from key_manager import generate_api_key

        key = generate_api_key(prefix="op")
        assert key.startswith("op_")

    def test_generate_key_uniqueness(self):
        from key_manager import generate_api_key

        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100  # All unique

    def test_create_key_entry_hash_only(self):
        from key_manager import create_key_entry

        entry = create_key_entry("pm_test", description="Test", store_hash_only=True)
        assert 'key_hash' in entry
        assert 'key' not in entry
        assert entry['description'] == "Test"
        assert entry['enabled'] is True

    def test_create_key_entry_with_expiry(self):
        from key_manager import create_key_entry

        before = time.time()
        entry = create_key_entry("pm_test", expires_in_days=30)
        expected_expiry = before + (30 * 86400)
        assert entry['expires_at'] >= expected_expiry - 1
        assert entry['expires_at'] <= expected_expiry + 2
