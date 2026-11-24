"""
Security regression tests for the auth proxy.

These run the real proxy against a fake upstream server, so they exercise the
whole path an attacker would use: raw request line -> middleware -> router ->
upstream request. Each test names the audit finding it guards (2026-11-05 audit).
"""

import asyncio
import importlib
import json
import os
import sys
from unittest.mock import patch

import aiohttp
import pytest
from aiohttp import web
from yarl import URL

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth-proxy'))

from tests.helpers import TEST_API_KEY, make_keys_file


UPSTREAM_CHAT_RESPONSE = {
    "model": "gpt-oss-120b",
    "choices": [{"message": {"role": "assistant", "content": "hi"}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
}


def _sse(events):
    """Encode a list of JSON-able objects (or the string '[DONE]') as an SSE body."""
    out = []
    for event in events:
        payload = event if isinstance(event, str) else json.dumps(event)
        out.append(f"data: {payload}\n\n")
    return "".join(out).encode()


STREAM_CHUNKS = [
    {"model": "gpt-oss-120b", "choices": [{"delta": {"content": "hi"}}]},
    {"model": "gpt-oss-120b", "choices": [],
     "usage": {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10}},
    "[DONE]",
]


@pytest.fixture
async def upstream(aiohttp_server):
    """A fake Privatemode binary that records every request it receives."""
    seen = []

    async def handler(request):
        body = await request.read()
        seen.append({
            'method': request.method,
            'raw_path': request.raw_path,
            'headers': dict(request.headers),
            'body': body,
        })
        if request.path.endswith('/chat/completions'):
            data = json.loads(body) if body else {}
            if isinstance(data, dict) and data.get('stream'):
                resp = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
                await resp.prepare(request)
                await resp.write(_sse(STREAM_CHUNKS))
                await resp.write_eof()
                return resp
            return web.json_response(
                UPSTREAM_CHAT_RESPONSE,
                headers={'Server': 'upstream/9.9', 'Set-Cookie': 'up=1'},
            )
        return web.json_response({"object": "list", "data": [{"id": "gpt-oss-120b"}]})

    app = web.Application()
    app.router.add_route('*', '/{tail:.*}', handler)
    server = await aiohttp_server(app)
    server.seen = seen
    return server


def _reload_app_modules(env):
    """Reload modules that read configuration at import time."""
    with patch.dict(os.environ, env):
        import config
        importlib.reload(config)
        import utils
        importlib.reload(utils)
        import usage_tracker
        importlib.reload(usage_tracker)
        import admin
        importlib.reload(admin)
        import server
        importlib.reload(server)
        return server, admin, usage_tracker


@pytest.fixture
def env_factory(tmp_path, upstream):
    def make(**overrides):
        env = {
            'API_KEYS_FILE': make_keys_file(tmp_path),
            'SETTINGS_FILE': os.path.join(str(tmp_path), 'settings.json'),
            'USAGE_FILE': os.path.join(str(tmp_path), 'usage.json'),
            'ADMIN_PASSWORD': 'test-admin-password',
            'PRIVATEMODE_API_KEY': 'pm_test_upstream_key',
            'UPSTREAM_URL': str(upstream.make_url('')).rstrip('/'),
            'TRUST_PROXY': 'false',
            'FORCE_HTTPS': 'false',
            'PBKDF2_SALT': 'test-salt-value-1234567890',
        }
        env.update(overrides)
        return env
    return make


@pytest.fixture
async def proxy(env_factory, aiohttp_client):
    """The real proxy app, pointed at the fake upstream."""
    env = env_factory()
    server, admin, usage_tracker = _reload_app_modules(env)
    with patch.dict(os.environ, env):
        client = await aiohttp_client(server.create_app())
        client.modules = (server, admin, usage_tracker)
        yield client


async def _raw_get(client, raw_path, method='GET', **kwargs):
    """Send a request whose path is NOT normalised by the client library."""
    base = str(client.make_url('/')).rstrip('/')
    async with aiohttp.ClientSession() as session:
        async with session.request(method, URL(base + raw_path, encoded=True), **kwargs) as resp:
            return resp.status, await resp.read()


# ── F1: /admin prefix must not bypass API-key authentication ──

class TestAdminPrefixBypass:

    @pytest.mark.parametrize('raw_path', [
        '/admin/../v1/models',
        '/admin/%2e%2e/v1/models',
        '/admin/%2E%2E/v1/models',
        '/admin/..%2fv1/models',
        '/admin/./../v1/models',
        '/adminx/../v1/models',
    ])
    async def test_dot_segment_paths_never_reach_upstream(self, proxy, upstream, raw_path):
        status, _ = await _raw_get(proxy, raw_path)
        assert status in (400, 401)
        assert upstream.seen == [], f"{raw_path} reached upstream without an API key"

    @pytest.mark.parametrize('path', ['/administrator', '/admin/x', '/admin-v1/models'])
    async def test_admin_lookalike_paths_require_api_key(self, proxy, upstream, path):
        resp = await proxy.get(path)
        assert resp.status == 401
        assert upstream.seen == []

    async def test_admin_pages_still_reachable_without_api_key(self, proxy, upstream):
        resp = await proxy.get('/admin/login')
        assert resp.status == 200
        assert upstream.seen == []

    async def test_authenticated_request_reaches_upstream_with_exact_path(self, proxy, upstream):
        resp = await proxy.get('/v1/models?limit=2',
                               headers={'Authorization': f'Bearer {TEST_API_KEY}'})
        assert resp.status == 200
        assert [r['raw_path'] for r in upstream.seen] == ['/v1/models?limit=2']

    async def test_dot_segments_rejected_even_with_valid_key(self, proxy, upstream):
        status, _ = await _raw_get(proxy, '/v1/../admin',
                                   headers={'Authorization': f'Bearer {TEST_API_KEY}'})
        assert status == 400
        assert upstream.seen == []


# ── helpers for admin flows ──

import re

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


async def _login(client, headers=None):
    page = await client.get('/admin/login', headers=headers)
    token = CSRF_RE.search(await page.text()).group(1)
    return await client.post('/admin/login', allow_redirects=False, headers=headers,
                             data={'password': 'test-admin-password', 'csrf_token': token})


async def _admin_csrf(client, path='/admin'):
    page = await client.get(path)
    assert page.status == 200
    return CSRF_RE.search(await page.text()).group(1)


@pytest.fixture
async def https_proxy(env_factory, aiohttp_client):
    """Proxy configured as in production behind one TLS-terminating proxy."""
    env = env_factory(FORCE_HTTPS='true', TRUST_PROXY='true')
    server, admin, usage_tracker = _reload_app_modules(env)
    with patch.dict(os.environ, env):
        yield await aiohttp_client(server.create_app())


# ── F3: admin session cookie must be Secure whenever HTTPS is served ──

class TestSessionCookie:

    async def test_cookie_secure_when_https(self, https_proxy):
        resp = await _login(https_proxy, headers={'X-Forwarded-Proto': 'https'})
        assert resp.status == 302
        cookie = resp.cookies['admin_session']
        assert cookie['secure'] is True
        assert cookie['httponly'] is True
        assert cookie['samesite'] == 'Strict'
        assert cookie['path'] == '/admin'

    async def test_cookie_secure_when_tls_terminates_in_app(self, env_factory, aiohttp_client):
        # The documented production setup: Let's Encrypt in the VM, no reverse
        # proxy, so browsers never send X-Forwarded-Proto. The old code then
        # issued a cookie without Secure (audit F3).
        env = env_factory(TLS_CERT_FILE='/certs/cert.pem', TLS_KEY_FILE='/certs/key.pem',
                          FORCE_HTTPS='false')
        server, _, _ = _reload_app_modules(env)
        with patch.dict(os.environ, env):
            client = await aiohttp_client(server.create_app())
            resp = await _login(client)
        assert resp.status == 302
        assert resp.cookies['admin_session']['secure'] is True

    async def test_forwarded_proto_ignored_without_trust_proxy(self, proxy):
        # Plain-HTTP local development: a client-sent header must not change anything
        resp = await _login(proxy, headers={'X-Forwarded-Proto': 'https'})
        assert resp.status == 302
        assert not resp.cookies['admin_session']['secure']


# ── Admin UI hardening ──

class TestAdminHardening:

    async def test_logout_requires_post_with_csrf(self, proxy):
        await _login(proxy)
        # A GET (e.g. an <img> on another site) no longer logs anyone out;
        # it is not an admin route, so it needs an API key like any other path.
        resp = await proxy.get('/admin/logout', allow_redirects=False)
        assert resp.status == 401
        assert (await proxy.get('/admin', allow_redirects=False)).status == 200

        bad = await proxy.post('/admin/logout', data={'csrf_token': 'nope'}, allow_redirects=False)
        assert bad.status == 403

        token = await _admin_csrf(proxy)
        out = await proxy.post('/admin/logout', data={'csrf_token': token}, allow_redirects=False)
        assert out.status == 302
        assert (await proxy.get('/admin', allow_redirects=False)).status == 302

    @pytest.mark.parametrize('page', ['/admin', '/admin/settings', '/admin/usage', '/admin/about'])
    async def test_admin_pages_have_no_inline_script(self, proxy, page):
        await _login(proxy)
        resp = await proxy.get(page)
        assert resp.status == 200
        html = await resp.text()
        csp = resp.headers['Content-Security-Policy']
        script_src = re.search(r"script-src ([^;]+)", csp).group(1)
        assert "'unsafe-inline'" not in script_src
        assert "object-src 'none'" in csp
        # Every script is external, and no inline event handlers remain
        assert re.findall(r'<script(?![^>]*\ssrc=)[^>]*>', html) == []
        assert re.findall(r'\son[a-z]+\s*=', html, re.I) == []

    async def test_admin_script_is_served(self, proxy):
        resp = await proxy.get('/admin/static/admin.js')
        assert resp.status == 200
        assert 'data-confirm' in await resp.text()

    async def test_about_page_renders_literal_braces_correctly(self, proxy):
        await _login(proxy)
        html = await (await proxy.get('/admin/about')).text()
        assert '{{' not in html

    async def test_login_error_shows_only_fixed_messages(self, proxy):
        resp = await proxy.get('/admin/login?error=Your+password+expired.+Email+it+to+x')
        assert 'Email it to' not in await resp.text()
        resp = await proxy.get('/admin/login?error=invalid')
        assert 'Invalid password' in await resp.text()

    async def test_bad_csrf_login_posts_hit_the_login_limit(self, proxy):
        # Forged/replayed login posts count as failed attempts (audit F2 note)
        for _ in range(5):
            resp = await proxy.post('/admin/login', allow_redirects=False,
                                    data={'password': 'x', 'csrf_token': 'forged'})
            assert resp.status == 302
        resp = await proxy.post('/admin/login', allow_redirects=False,
                                data={'password': 'x', 'csrf_token': 'forged'})
        assert resp.status == 429

    async def test_admin_routes_are_ip_rate_limited(self, env_factory, aiohttp_client, tmp_path):
        # /admin used to skip the per-IP limit entirely (audit F5)
        env = env_factory()
        with open(env['SETTINGS_FILE'], 'w') as f:
            json.dump({'ip_rate_limit_requests': 3, 'ip_rate_limit_window': 60}, f)
        server, _, _ = _reload_app_modules(env)
        with patch.dict(os.environ, env):
            client = await aiohttp_client(server.create_app())
            statuses = [(await client.get('/admin/login')).status for _ in range(4)]
        assert statuses == [200, 200, 200, 429]

    async def test_rate_limit_settings_reject_zero_and_negative(self, proxy):
        await _login(proxy)
        token = await _admin_csrf(proxy, '/admin/settings')
        await proxy.post('/admin/settings/rate-limits', allow_redirects=False, data={
            'csrf_token': token, 'rate_limit_requests': '0',
            'ip_rate_limit_requests': '-5', 'rate_limit_window': '120',
        })
        settings = proxy.modules[1].load_settings()
        assert settings['rate_limit_requests'] == 100      # unchanged default
        assert settings['ip_rate_limit_requests'] == 1000  # unchanged default
        assert settings['rate_limit_window'] == 120        # valid value applied

    async def test_admin_events_logged_without_ip(self, proxy, capsys):
        await proxy.post('/admin/login', allow_redirects=False,
                         data={'password': 'x', 'csrf_token': 'forged'})
        page = await proxy.get('/admin/login')
        token = CSRF_RE.search(await page.text()).group(1)
        await proxy.post('/admin/login', allow_redirects=False,
                         data={'password': 'wrong', 'csrf_token': token})
        events = [json.loads(line) for line in capsys.readouterr().out.splitlines()
                  if line.startswith('{"security_event"') or '"security_event"' in line]
        assert {'admin_login_failure'} <= {e['security_event'] for e in events}
        assert all('127.0.0.1' not in json.dumps(e) for e in events)


# ── Proxy header handling ──

class TestHeaderFiltering:

    async def test_credentials_and_client_details_not_sent_upstream(self, proxy, upstream):
        resp = await proxy.get('/v1/models', headers={
            'Authorization': f'Bearer {TEST_API_KEY}',
            'Cookie': 'admin_session=secret-session',
            'X-Forwarded-For': '203.0.113.5',
            'X-Real-IP': '203.0.113.5',
        })
        assert resp.status == 200
        sent = {k.lower(): v for k, v in upstream.seen[0]['headers'].items()}
        for header in ('authorization', 'x-api-key', 'cookie', 'x-forwarded-for', 'x-real-ip'):
            assert header not in sent, header

    async def test_upstream_cookies_and_server_header_not_returned(self, proxy):
        resp = await proxy.post('/v1/chat/completions',
                                headers={'Authorization': f'Bearer {TEST_API_KEY}'},
                                json={'model': 'gpt-oss-120b', 'messages': []})
        assert resp.status == 200
        assert 'Set-Cookie' not in resp.headers
        assert 'Server' not in resp.headers

    async def test_no_server_version_header(self, proxy):
        resp = await proxy.get('/health')
        assert 'Server' not in resp.headers


# ── Usage metering ──

class TestMetering:

    async def test_non_streaming_usage_recorded(self, proxy):
        await proxy.post('/v1/chat/completions',
                         headers={'Authorization': f'Bearer {TEST_API_KEY}'},
                         json={'model': 'gpt-oss-120b', 'messages': []})
        summary = proxy.modules[2].get_tracker().get_usage_summary()
        assert summary['requests'] == 1
        assert summary['total_tokens'] == 5

    async def test_streaming_usage_recorded_and_extra_chunk_hidden(self, proxy, upstream):
        resp = await proxy.post('/v1/chat/completions',
                                headers={'Authorization': f'Bearer {TEST_API_KEY}'},
                                json={'model': 'gpt-oss-120b', 'messages': [], 'stream': True})
        assert resp.status == 200
        body = (await resp.read()).decode()
        # The proxy asked the upstream for usage on the client's behalf...
        sent = json.loads(upstream.seen[0]['body'])
        assert sent['stream_options'] == {'include_usage': True}
        # ...and hid the extra usage chunk the client did not ask for
        assert '"usage"' not in body
        assert '"content": "hi"' in body and 'data: [DONE]' in body
        summary = proxy.modules[2].get_tracker().get_usage_summary()
        assert summary['requests'] == 1
        assert summary['total_tokens'] == 10

    async def test_streaming_usage_chunk_kept_when_client_asked(self, proxy):
        resp = await proxy.post('/v1/chat/completions',
                                headers={'Authorization': f'Bearer {TEST_API_KEY}'},
                                json={'model': 'gpt-oss-120b', 'messages': [], 'stream': True,
                                      'stream_options': {'include_usage': True}})
        assert '"usage"' in (await resp.read()).decode()

    async def test_non_object_json_body_does_not_crash(self, proxy):
        resp = await proxy.post('/v1/chat/completions',
                                headers={'Authorization': f'Bearer {TEST_API_KEY}'},
                                data=b'[1, 2, 3]')
        assert resp.status == 200

    def test_null_usage_does_not_raise(self):
        server = sys.modules['server']
        usage = server.extract_usage_from_response(
            json.dumps({'model': 'gpt-oss-120b', 'usage': None}).encode(), 'chat')
        assert usage['total_tokens'] == 0
        assert usage['model'] == 'gpt-oss-120b'
