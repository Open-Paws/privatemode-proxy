"""
Shared fixtures for privatemode-proxy tests.

Sets up the aiohttp test app with mocked dependencies so tests
can run without external services (Privatemode API, filesystem, etc).
"""

import os
import sys
from unittest.mock import patch

import pytest

# Add auth-proxy to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))


# ── Environment setup (must happen before importing app modules) ──

# Provide required env vars before any module-level code runs.
# PBKDF2_SALT must be >= 16 bytes or admin.py raises ValueError at import time.
os.environ.setdefault('PBKDF2_SALT', 'test-salt-value-1234567890')
os.environ.setdefault('ADMIN_PASSWORD', 'test-admin-password')
os.environ.setdefault('PRIVATEMODE_API_KEY', 'pm_test_upstream_key')
os.environ.setdefault('API_KEYS_FILE', '')
os.environ.setdefault('SETTINGS_FILE', '')
os.environ.setdefault('USAGE_FILE', '')
os.environ.setdefault('UPSTREAM_URL', 'http://localhost:19999')
os.environ.setdefault('TRUST_PROXY', 'false')
os.environ.setdefault('FORCE_HTTPS', 'false')

from tests.helpers import make_keys_file


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def keys_file(tmp_path):
    """Create a keys file with test data and return its path."""
    return make_keys_file(tmp_path)


@pytest.fixture
def settings_file(tmp_path):
    """Create a settings file path (initially nonexistent)."""
    return os.path.join(str(tmp_path), "settings.json")


@pytest.fixture
def usage_file(tmp_path):
    """Create a usage file path (initially nonexistent)."""
    return os.path.join(str(tmp_path), "usage.json")


@pytest.fixture
def app_env(keys_file, settings_file, usage_file):
    """
    Patch environment variables for the test app.
    Returns a dict of the env vars set.
    """
    env = {
        'API_KEYS_FILE': keys_file,
        'SETTINGS_FILE': settings_file,
        'USAGE_FILE': usage_file,
        'ADMIN_PASSWORD': 'test-admin-password',
        'PRIVATEMODE_API_KEY': 'pm_test_upstream_key',
        'UPSTREAM_URL': 'http://localhost:19999',
        'TRUST_PROXY': 'false',
        'FORCE_HTTPS': 'false',
        'PBKDF2_SALT': 'test-salt-value-1234567890',
    }
    with patch.dict(os.environ, env):
        yield env
