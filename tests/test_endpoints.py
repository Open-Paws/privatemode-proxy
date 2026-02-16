"""
Integration tests for HTTP endpoints using aiohttp test client.

Tests the full request/response cycle through middleware and handlers.
"""

import json
import os
import sys
import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, TestClient, TestServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))

from tests.helpers import TEST_API_KEY, make_keys_file


@pytest.fixture
def proxy_app(tmp_path):
    """Create a test app with mocked config."""
    keys_file = make_keys_file(tmp_path)
    settings_file = os.path.join(str(tmp_path), "settings.json")
    usage_file = os.path.join(str(tmp_path), "usage.json")

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
        # Re-import to pick up new config values
        import importlib
        import config
        importlib.reload(config)

        # Need to reload server module too since it imports config at module level
        import server
        importlib.reload(server)

        application = server.create_app()
        yield application


@pytest.fixture
async def client(proxy_app, aiohttp_client):
    """Create a test client."""
    return await aiohttp_client(proxy_app)


class TestHealthEndpoint:
    """Test the /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get('/health')
        assert resp.status == 200
        data = await resp.json()
        assert data['status'] == 'healthy'

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client):
        # No auth headers at all
        resp = await client.get('/health')
        assert resp.status == 200


class TestAuthMiddleware:
    """Test authentication middleware on proxy endpoints."""

    @pytest.mark.asyncio
    async def test_missing_api_key(self, client):
        resp = await client.post('/v1/chat/completions',
                                  json={"model": "test", "messages": []})
        assert resp.status == 401
        data = await resp.json()
        assert 'Missing API key' in data['error']

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, client):
        resp = await client.post('/v1/chat/completions',
                                  headers={'Authorization': 'Bearer pm_invalid_key'},
                                  json={"model": "test", "messages": []})
        assert resp.status == 401
        data = await resp.json()
        assert 'Invalid' in data['error']

    @pytest.mark.asyncio
    async def test_valid_api_key_bearer(self, client):
        # This will try to proxy to upstream (which doesn't exist in test)
        # but should get past auth
        with patch('server.proxy_request', new_callable=AsyncMock) as mock_proxy:
            mock_proxy.return_value = web.json_response({"ok": True})
            resp = await client.post(
                '/v1/chat/completions',
                headers={'Authorization': f'Bearer {TEST_API_KEY}'},
                json={"model": "test", "messages": []},
            )
            # Should get past auth (200 from mocked proxy or 502 if proxy fails)
            assert resp.status in (200, 502)

    @pytest.mark.asyncio
    async def test_valid_api_key_x_header(self, client):
        with patch('server.proxy_request', new_callable=AsyncMock) as mock_proxy:
            mock_proxy.return_value = web.json_response({"ok": True})
            resp = await client.post(
                '/v1/chat/completions',
                headers={'X-API-Key': TEST_API_KEY},
                json={"model": "test", "messages": []},
            )
            assert resp.status in (200, 502)


class TestKeyInfoEndpoint:
    """Test the /auth/key-info endpoint."""

    @pytest.mark.asyncio
    async def test_key_info_valid(self, client):
        resp = await client.get('/auth/key-info',
                                 headers={'Authorization': f'Bearer {TEST_API_KEY}'})
        assert resp.status == 200
        data = await resp.json()
        assert data['key_id'] == 'test_key_1'

    @pytest.mark.asyncio
    async def test_key_info_invalid(self, client):
        resp = await client.get('/auth/key-info',
                                 headers={'Authorization': 'Bearer pm_bad'})
        assert resp.status == 401

    @pytest.mark.asyncio
    async def test_key_info_no_auth(self, client):
        resp = await client.get('/auth/key-info')
        assert resp.status == 401


class TestSecurityHeaders:
    """Test that security headers are set on responses."""

    @pytest.mark.asyncio
    async def test_health_has_security_headers(self, client):
        resp = await client.get('/health')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
        assert resp.headers.get('X-Frame-Options') == 'DENY'
        assert resp.headers.get('X-XSS-Protection') == '1; mode=block'
        assert 'Referrer-Policy' in resp.headers
        assert 'Permissions-Policy' in resp.headers

    @pytest.mark.asyncio
    async def test_admin_has_csp(self, client):
        # Admin login page should have CSP
        resp = await client.get('/admin/login')
        assert resp.status == 200
        csp = resp.headers.get('Content-Security-Policy', '')
        assert "frame-ancestors 'none'" in csp


class TestAdminEndpoints:
    """Test admin UI endpoints."""

    @pytest.mark.asyncio
    async def test_admin_redirects_to_login(self, client):
        resp = await client.get('/admin', allow_redirects=False)
        assert resp.status == 302
        assert '/admin/login' in resp.headers['Location']

    @pytest.mark.asyncio
    async def test_login_page_loads(self, client):
        resp = await client.get('/admin/login')
        assert resp.status == 200
        text = await resp.text()
        assert 'password' in text.lower()
        assert 'csrf_token' in text

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        # First get a CSRF token
        resp = await client.get('/admin/login')
        text = await resp.text()
        # Extract CSRF token from form
        import re
        match = re.search(r'name="csrf_token" value="([^"]+)"', text)
        assert match, "CSRF token not found in login form"
        csrf_token = match.group(1)

        resp = await client.post('/admin/login', data={
            'password': 'wrong',
            'csrf_token': csrf_token,
        }, allow_redirects=False)
        assert resp.status == 302
        assert 'error' in resp.headers.get('Location', '')

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        # Get CSRF token
        resp = await client.get('/admin/login')
        text = await resp.text()
        import re
        match = re.search(r'name="csrf_token" value="([^"]+)"', text)
        csrf_token = match.group(1)

        resp = await client.post('/admin/login', data={
            'password': 'test-admin-password',
            'csrf_token': csrf_token,
        }, allow_redirects=False)
        assert resp.status == 302
        assert resp.headers.get('Location') == '/admin'
        # Should have session cookie
        cookies = resp.cookies
        assert 'admin_session' in {c.key for c in resp.cookies.values()} or resp.headers.get('Set-Cookie', '')
