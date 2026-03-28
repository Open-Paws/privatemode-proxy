"""
Tests for utility functions.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))

from utils import get_client_ip


class TestGetClientIP:
    """Test client IP extraction with proxy trust settings."""

    def test_direct_connection(self):
        request = MagicMock()
        request.remote = "192.168.1.1"
        request.headers = MagicMock()
        request.headers.get = lambda key, default='': ''

        with patch('utils.TRUST_PROXY', False):
            assert get_client_ip(request) == "192.168.1.1"

    def test_ignores_forwarded_when_untrusted(self):
        request = MagicMock()
        request.remote = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = lambda key, default='': (
            "1.2.3.4, 5.6.7.8" if key == 'X-Forwarded-For' else ''
        )

        with patch('utils.TRUST_PROXY', False):
            assert get_client_ip(request) == "10.0.0.1"

    def test_uses_forwarded_when_trusted(self):
        request = MagicMock()
        request.remote = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = lambda key, default='': (
            "1.2.3.4, 5.6.7.8" if key == 'X-Forwarded-For' else ''
        )

        with patch('utils.TRUST_PROXY', True):
            assert get_client_ip(request) == "1.2.3.4"

    def test_single_forwarded_ip(self):
        request = MagicMock()
        request.remote = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = lambda key, default='': (
            "203.0.113.50" if key == 'X-Forwarded-For' else ''
        )

        with patch('utils.TRUST_PROXY', True):
            assert get_client_ip(request) == "203.0.113.50"

    def test_no_remote_returns_unknown(self):
        request = MagicMock()
        request.remote = None
        request.headers = MagicMock()
        request.headers.get = lambda key, default='': ''

        with patch('utils.TRUST_PROXY', False):
            assert get_client_ip(request) == "unknown"

    def test_forwarded_with_spaces(self):
        request = MagicMock()
        request.remote = "10.0.0.1"
        request.headers = MagicMock()
        request.headers.get = lambda key, default='': (
            "  1.2.3.4 , 5.6.7.8 " if key == 'X-Forwarded-For' else ''
        )

        with patch('utils.TRUST_PROXY', True):
            assert get_client_ip(request) == "1.2.3.4"
