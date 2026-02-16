"""
Shared test constants and helper functions.
"""

import hashlib
import json
import os
import time


# ── Test API key constants ──

TEST_API_KEY = "pm_test-key-for-unit-tests-12345"
TEST_API_KEY_HASH = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()
TEST_API_KEY_2 = "pm_second-test-key-67890"
TEST_API_KEY_2_HASH = hashlib.sha256(TEST_API_KEY_2.encode()).hexdigest()
EXPIRED_API_KEY = "pm_expired-key-99999"
EXPIRED_API_KEY_HASH = hashlib.sha256(EXPIRED_API_KEY.encode()).hexdigest()
DISABLED_API_KEY = "pm_disabled-key-00000"
DISABLED_API_KEY_HASH = hashlib.sha256(DISABLED_API_KEY.encode()).hexdigest()


def make_keys_file(tmp_path, keys=None):
    """Create a temporary API keys JSON file."""
    if keys is None:
        keys = [
            {
                "key_id": "test_key_1",
                "key_hash": TEST_API_KEY_HASH,
                "created_at": time.time(),
                "description": "Test key 1",
                "enabled": True,
            },
            {
                "key_id": "test_key_2",
                "key_hash": TEST_API_KEY_2_HASH,
                "created_at": time.time(),
                "description": "Test key 2 with rate limit",
                "enabled": True,
                "rate_limit": 5,
            },
            {
                "key_id": "expired_key",
                "key_hash": EXPIRED_API_KEY_HASH,
                "created_at": time.time() - 86400,
                "expires_at": time.time() - 3600,  # Expired 1 hour ago
                "description": "Expired key",
                "enabled": True,
            },
            {
                "key_id": "disabled_key",
                "key_hash": DISABLED_API_KEY_HASH,
                "created_at": time.time(),
                "description": "Disabled key",
                "enabled": False,
            },
        ]

    keys_file = os.path.join(str(tmp_path), "api_keys.json")
    with open(keys_file, "w") as f:
        json.dump({"keys": keys}, f)
    return keys_file
