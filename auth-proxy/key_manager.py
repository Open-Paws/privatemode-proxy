"""
API Key Manager with rotation support.

Supports multiple valid keys with metadata including:
- Key ID for tracking/revocation
- Creation timestamp
- Expiration timestamp (optional)
- Rate limit overrides (optional)
- Description/owner info
"""

import json
import hashlib
import secrets
import time
import threading
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class APIKey:
    """Represents an API key with metadata."""
    key_id: str
    key_hash: str  # We store hash, not plaintext
    created_at: float
    expires_at: Optional[float] = None
    rate_limit: Optional[int] = None
    description: str = ""
    enabled: bool = True

    def is_valid(self) -> bool:
        """Check if key is valid (enabled and not expired)."""
        if not self.enabled:
            return False
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True


class KeyManager:
    """Manages API keys with hot-reload support."""

    def __init__(self, keys_file: str):
        self.keys_file = keys_file
        self.keys: dict[str, APIKey] = {}  # key_hash -> APIKey
        self._lock = threading.RLock()
        self._last_modified = 0
        self._load_keys()

    def _hash_key(self, key: str) -> str:
        """Hash an API key for secure storage/comparison."""
        return hashlib.sha256(key.encode()).hexdigest()

    def _load_keys_from_env(self) -> None:
        """Load keys from environment variables (for cloud deployment)."""
        # API_KEYS env var: comma-separated list of keys
        env_keys = os.environ.get('API_KEYS', '')
        if not env_keys:
            return

        with self._lock:
            for i, key in enumerate(env_keys.split(',')):
                key = key.strip()
                if not key:
                    continue
                key_hash = self._hash_key(key)
                api_key = APIKey(
                    key_id=f"env_key_{i}",
                    key_hash=key_hash,
                    created_at=time.time(),
                    description="From API_KEYS environment variable",
                    enabled=True
                )
                self.keys[key_hash] = api_key

            if self.keys:
                print(f"Loaded {len(self.keys)} API keys from environment")

    def _load_keys(self) -> None:
        """Load keys from file and/or environment."""
        # First try environment variables (for cloud deployment)
        self._load_keys_from_env()

        # Then try file (can add more keys or override)
        if not os.path.exists(self.keys_file):
            if not self.keys:
                print(f"Warning: Keys file {self.keys_file} not found and no API_KEYS env var set")
            return

        try:
            mtime = os.path.getmtime(self.keys_file)
            if mtime <= self._last_modified:
                return

            with open(self.keys_file, 'r') as f:
                data = json.load(f)

            with self._lock:
                self.keys.clear()
                for key_data in data.get('keys', []):
                    # Support both hashed and plaintext keys in config
                    if 'key_hash' in key_data:
                        key_hash = key_data['key_hash']
                    elif 'key' in key_data:
                        key_hash = self._hash_key(key_data['key'])
                    else:
                        continue

                    api_key = APIKey(
                        key_id=key_data.get('key_id', key_hash[:8]),
                        key_hash=key_hash,
                        created_at=key_data.get('created_at', time.time()),
                        expires_at=key_data.get('expires_at'),
                        rate_limit=key_data.get('rate_limit'),
                        description=key_data.get('description', ''),
                        enabled=key_data.get('enabled', True)
                    )
                    self.keys[key_hash] = api_key

                self._last_modified = mtime
                print(f"Loaded {len(self.keys)} API keys")

        except Exception as e:
            print(f"Error loading keys: {e}")

    def reload_if_changed(self) -> None:
        """Reload keys if file has changed (for hot-reload)."""
        try:
            if os.path.exists(self.keys_file):
                mtime = os.path.getmtime(self.keys_file)
                if mtime > self._last_modified:
                    self._load_keys()
        except Exception as e:
            print(f"Error checking keys file: {e}")

    def validate_key(self, key: str) -> tuple[bool, Optional[APIKey]]:
        """
        Validate an API key.
        Returns (is_valid, api_key_obj or None).
        """
        self.reload_if_changed()

        key_hash = self._hash_key(key)
        with self._lock:
            api_key = self.keys.get(key_hash)
            if api_key and api_key.is_valid():
                return True, api_key
        return False, None

    def get_key_info(self, key: str) -> Optional[dict]:
        """Get non-sensitive info about a key."""
        valid, api_key = self.validate_key(key)
        if not valid or not api_key:
            return None
        return {
            'key_id': api_key.key_id,
            'created_at': api_key.created_at,
            'expires_at': api_key.expires_at,
            'rate_limit': api_key.rate_limit,
            'description': api_key.description
        }


def generate_api_key(prefix: str = "pm") -> str:
    """Generate a new secure API key."""
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


def create_key_entry(
    key: str,
    description: str = "",
    expires_in_days: Optional[int] = None,
    rate_limit: Optional[int] = None,
    store_hash_only: bool = True
) -> dict:
    """Create a key entry for the keys file."""
    entry = {
        'key_id': f"key_{secrets.token_hex(4)}",
        'created_at': time.time(),
        'description': description,
        'enabled': True
    }

    if store_hash_only:
        entry['key_hash'] = hashlib.sha256(key.encode()).hexdigest()
    else:
        entry['key'] = key

    if expires_in_days:
        entry['expires_at'] = time.time() + (expires_in_days * 86400)

    if rate_limit:
        entry['rate_limit'] = rate_limit

    return entry
