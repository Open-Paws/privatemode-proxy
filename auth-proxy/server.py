"""
Authentication Proxy Server for Privatemode.

This server sits in front of the Privatemode proxy and provides:
- API key authentication
- Rate limiting
- Request logging
- Token usage tracking
- Key rotation support via hot-reload
"""

import ssl
import time
import json
import asyncio
from collections import defaultdict
from aiohttp import web, ClientSession, ClientTimeout
from key_manager import KeyManager
from admin import setup_admin_routes, load_settings
from usage_tracker import get_tracker
from config import (
    API_KEYS_FILE, UPSTREAM_URL, PORT, PRIVATEMODE_API_KEY,
    DEFAULT_RATE_LIMIT_REQUESTS, DEFAULT_RATE_LIMIT_WINDOW,
    DEFAULT_IP_RATE_LIMIT_REQUESTS, DEFAULT_IP_RATE_LIMIT_WINDOW,
    TLS_ENABLED, TLS_CERT_FILE, TLS_KEY_FILE, FORCE_HTTPS, TRUST_PROXY
)
from utils import get_client_ip


def get_rate_limit_settings() -> dict:
    """Get current rate limit settings from settings file or defaults."""
    settings = load_settings()
    return {
        'rate_limit_requests': settings.get('rate_limit_requests', DEFAULT_RATE_LIMIT_REQUESTS),
        'rate_limit_window': settings.get('rate_limit_window', DEFAULT_RATE_LIMIT_WINDOW),
        'ip_rate_limit_requests': settings.get('ip_rate_limit_requests', DEFAULT_IP_RATE_LIMIT_REQUESTS),
        'ip_rate_limit_window': settings.get('ip_rate_limit_window', DEFAULT_IP_RATE_LIMIT_WINDOW),
    }

# Rate limiting storage: key_id -> list of request timestamps
rate_limit_store: dict[str, list[float]] = defaultdict(list)

# Global rate limiting storage (shared across ALL keys)
global_rate_limit_store: list[float] = []

# IP rate limiting storage
ip_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def extract_api_key(request: web.Request) -> str | None:
    """Extract API key from request headers."""
    # Check Authorization header (Bearer token)
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:]

    # Check X-API-Key header
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return api_key

    return None


def check_global_rate_limit() -> tuple[bool, int, int, int]:
    """
    Check if global rate limit (across ALL keys) is exceeded.
    Returns (is_allowed, remaining_requests, limit, window).
    """
    global global_rate_limit_store
    settings = get_rate_limit_settings()
    limit = settings['rate_limit_requests']
    window = settings['rate_limit_window']

    now = time.time()
    window_start = now - window

    # Clean old entries
    global_rate_limit_store = [ts for ts in global_rate_limit_store if ts > window_start]

    current_count = len(global_rate_limit_store)
    remaining = max(0, limit - current_count)

    if current_count >= limit:
        return False, 0, limit, window

    global_rate_limit_store.append(now)
    return True, remaining - 1, limit, window


def check_per_key_rate_limit(key_id: str, limit: int | None) -> tuple[bool, int, int]:
    """
    Check if per-key rate limit is exceeded.
    Returns (is_allowed, remaining_requests, configured_limit).
    Only applies if the key has a specific rate limit set.
    """
    if limit is None:
        # No per-key limit set, always allowed (global limit handles it)
        return True, -1, 0

    settings = get_rate_limit_settings()
    window = settings['rate_limit_window']

    now = time.time()
    window_start = now - window

    # Clean old entries
    rate_limit_store[key_id] = [
        ts for ts in rate_limit_store[key_id] if ts > window_start
    ]

    current_count = len(rate_limit_store[key_id])
    remaining = max(0, limit - current_count)

    if current_count >= limit:
        return False, 0, limit

    rate_limit_store[key_id].append(now)
    return True, remaining - 1, limit


def check_ip_rate_limit(ip: str) -> tuple[bool, int, int, int]:
    """Check if IP is within global rate limit. Returns (allowed, remaining, limit, window)."""
    settings = get_rate_limit_settings()
    ip_limit = settings['ip_rate_limit_requests']
    ip_window = settings['ip_rate_limit_window']

    now = time.time()
    window_start = now - ip_window

    # Clean old entries
    ip_rate_limit_store[ip] = [ts for ts in ip_rate_limit_store[ip] if ts > window_start]

    current_count = len(ip_rate_limit_store[ip])
    remaining = max(0, ip_limit - current_count)

    if current_count >= ip_limit:
        return False, 0, ip_limit, ip_window

    ip_rate_limit_store[ip].append(now)
    return True, remaining - 1, ip_limit, ip_window


def detect_endpoint_type(path: str) -> str:
    """Detect the API endpoint type from path."""
    if '/chat/completions' in path:
        return 'chat'
    elif '/embeddings' in path:
        return 'embeddings'
    elif '/audio/transcriptions' in path:
        return 'transcriptions'
    elif '/completions' in path:
        return 'completions'
    return 'other'


def extract_model_from_request(body: bytes) -> str:
    """Extract model name from request body."""
    try:
        data = json.loads(body)
        return data.get('model', 'unknown')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 'unknown'


def extract_usage_from_response(response_body: bytes, endpoint: str) -> dict:
    """
    Extract token usage from response body.
    Only extracts usage metadata, never the actual content.
    """
    usage = {
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'total_tokens': 0,
        'model': 'unknown'
    }

    try:
        data = json.loads(response_body)

        # Get model from response
        usage['model'] = data.get('model', 'unknown')

        # Chat completions and completions have usage object
        if 'usage' in data:
            usage_data = data['usage']
            usage['prompt_tokens'] = usage_data.get('prompt_tokens', 0)
            usage['completion_tokens'] = usage_data.get('completion_tokens', 0)
            usage['total_tokens'] = usage_data.get('total_tokens', 0)

        # Embeddings also have usage
        elif endpoint == 'embeddings' and 'usage' in data:
            usage_data = data['usage']
            usage['total_tokens'] = usage_data.get('total_tokens', 0)
            usage['prompt_tokens'] = usage_data.get('prompt_tokens', usage['total_tokens'])

    except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
        pass

    return usage


async def proxy_request(request: web.Request, session: ClientSession) -> web.Response:
    """Proxy the request to upstream Privatemode proxy."""
    # Build upstream URL
    path = request.path
    if request.query_string:
        path = f"{path}?{request.query_string}"
    upstream_url = f"{UPSTREAM_URL}{path}"

    # Forward headers (excluding hop-by-hop headers)
    headers = {}
    hop_by_hop = {'connection', 'keep-alive', 'proxy-authenticate',
                  'proxy-authorization', 'te', 'trailers', 'transfer-encoding',
                  'upgrade', 'host'}

    for key, value in request.headers.items():
        if key.lower() not in hop_by_hop:
            # Don't forward our auth headers to upstream
            if key.lower() not in ('authorization', 'x-api-key'):
                headers[key] = value

    # Add Privatemode API key for upstream authentication
    if PRIVATEMODE_API_KEY:
        headers['Authorization'] = f'Bearer {PRIVATEMODE_API_KEY}'

    # Read request body
    body = await request.read()

    # Detect endpoint type and model for usage tracking
    endpoint = detect_endpoint_type(path)
    request_model = extract_model_from_request(body) if body else 'unknown'

    # Track audio file size for transcription requests
    audio_bytes = 0
    if endpoint == 'transcriptions':
        audio_bytes = len(body)

    try:
        # Forward request to upstream
        async with session.request(
            method=request.method,
            url=upstream_url,
            headers=headers,
            data=body,
            allow_redirects=False
        ) as upstream_response:
            # Read response
            response_body = await upstream_response.read()

            # Build response headers
            response_headers = {}
            for key, value in upstream_response.headers.items():
                if key.lower() not in hop_by_hop:
                    response_headers[key] = value

            # Track usage if request was successful and we have a key_id
            if upstream_response.status == 200 and 'key_id' in request:
                usage = extract_usage_from_response(response_body, endpoint)
                model = usage['model'] if usage['model'] != 'unknown' else request_model

                tracker = get_tracker()
                tracker.record_usage(
                    key_id=request['key_id'],
                    model=model,
                    endpoint=endpoint,
                    prompt_tokens=usage['prompt_tokens'],
                    completion_tokens=usage['completion_tokens'],
                    total_tokens=usage['total_tokens'],
                    audio_bytes=audio_bytes
                )

            return web.Response(
                status=upstream_response.status,
                headers=response_headers,
                body=response_body
            )

    except asyncio.TimeoutError:
        return web.json_response(
            {'error': 'Upstream timeout'},
            status=504
        )
    except Exception as e:
        print(f"Proxy error: {e}")
        return web.json_response(
            {'error': 'Proxy error'},
            status=502
        )


@web.middleware
async def https_enforcement_middleware(request: web.Request, handler):
    """Enforce HTTPS connections when FORCE_HTTPS is enabled."""
    if not FORCE_HTTPS:
        return await handler(request)

    # Check if request is over HTTPS
    is_https = request.secure  # True if connection is TLS

    # If behind a trusted proxy, also check X-Forwarded-Proto
    if not is_https and TRUST_PROXY:
        forwarded_proto = request.headers.get('X-Forwarded-Proto', '')
        is_https = forwarded_proto.lower() == 'https'

    # Allow health checks over HTTP for internal load balancer probes
    if request.path == '/health':
        return await handler(request)

    if not is_https:
        return web.json_response(
            {'error': 'HTTPS required. Please use a secure connection.'},
            status=403
        )

    return await handler(request)


@web.middleware
async def security_headers_middleware(request: web.Request, handler):
    """Add security headers to all responses."""
    response = await handler(request)

    # Content Security Policy - restrictive for admin UI
    if request.path.startswith('/admin'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )

    # Prevent MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'

    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'

    # XSS protection (legacy, but still useful for older browsers)
    response.headers['X-XSS-Protection'] = '1; mode=block'

    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Permissions policy (restrict sensitive APIs)
    response.headers['Permissions-Policy'] = (
        'geolocation=(), microphone=(), camera=()'
    )

    # HSTS - enforce HTTPS for 1 year when TLS is enabled
    if TLS_ENABLED or FORCE_HTTPS:
        response.headers['Strict-Transport-Security'] = (
            'max-age=31536000; includeSubDomains'
        )

    return response


def create_auth_middleware(key_manager: KeyManager):
    """Create authentication middleware."""

    @web.middleware
    async def auth_middleware(request: web.Request, handler):
        # Skip auth for health check and admin routes
        if request.path == '/health' or request.path.startswith('/admin'):
            return await handler(request)

        # Check global IP rate limit first
        client_ip = get_client_ip(request)
        ip_allowed, ip_remaining, ip_limit, ip_window = check_ip_rate_limit(client_ip)
        if not ip_allowed:
            return web.json_response(
                {'error': 'Global rate limit exceeded'},
                status=429,
                headers={
                    'X-RateLimit-Limit': str(ip_limit),
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(int(time.time()) + ip_window)
                }
            )

        # Extract and validate API key
        api_key = extract_api_key(request)
        if not api_key:
            return web.json_response(
                {'error': 'Missing API key. Use Authorization: Bearer <key> or X-API-Key header'},
                status=401
            )

        valid, key_obj = key_manager.validate_key(api_key)
        if not valid:
            return web.json_response(
                {'error': 'Invalid or expired API key'},
                status=401
            )

        # Check global rate limit first (shared across ALL keys)
        global_allowed, global_remaining, global_limit, global_window = check_global_rate_limit()
        if not global_allowed:
            return web.json_response(
                {'error': 'Global rate limit exceeded'},
                status=429,
                headers={
                    'X-RateLimit-Limit': str(global_limit),
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(int(time.time()) + global_window)
                }
            )

        # Check per-key rate limit (only if key has a specific limit set)
        per_key_limit = key_obj.rate_limit if key_obj else None
        key_allowed, key_remaining, key_limit = check_per_key_rate_limit(key_obj.key_id, per_key_limit)

        if not key_allowed:
            return web.json_response(
                {'error': 'Per-key rate limit exceeded'},
                status=429,
                headers={
                    'X-RateLimit-Limit': str(key_limit),
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(int(time.time()) + global_window)
                }
            )

        # Add rate limit headers to request for handler
        # Show per-key limit if set, otherwise show global
        if per_key_limit:
            request['rate_limit_remaining'] = key_remaining
            request['rate_limit_limit'] = key_limit
        else:
            request['rate_limit_remaining'] = global_remaining
            request['rate_limit_limit'] = global_limit
        request['key_id'] = key_obj.key_id

        return await handler(request)

    return auth_middleware


async def health_handler(request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({'status': 'healthy'})


async def key_info_handler(request: web.Request) -> web.Response:
    """Return info about the current API key (non-sensitive)."""
    key_manager = request.app['key_manager']
    api_key = extract_api_key(request)

    if not api_key:
        return web.json_response({'error': 'No API key provided'}, status=401)

    info = key_manager.get_key_info(api_key)
    if not info:
        return web.json_response({'error': 'Invalid API key'}, status=401)

    return web.json_response(info)


async def catch_all_handler(request: web.Request) -> web.Response:
    """Proxy all other requests to upstream."""
    session = request.app['client_session']

    response = await proxy_request(request, session)

    # Add rate limit headers
    if 'rate_limit_remaining' in request:
        response.headers['X-RateLimit-Remaining'] = str(request['rate_limit_remaining'])
        response.headers['X-RateLimit-Limit'] = str(request.get('rate_limit_limit', 100))

    return response


async def on_startup(app: web.Application):
    """Initialize client session on startup."""
    timeout = ClientTimeout(total=300)  # 5 minute timeout for LLM requests
    app['client_session'] = ClientSession(timeout=timeout)
    print(f"Auth proxy started, forwarding to {UPSTREAM_URL}")


async def on_cleanup(app: web.Application):
    """Cleanup client session and flush usage data."""
    await app['client_session'].close()
    # Flush usage data to disk
    get_tracker().flush()


def create_app() -> web.Application:
    """Create the application."""
    key_manager = KeyManager(API_KEYS_FILE)

    # Middleware order: HTTPS enforcement -> security headers -> auth
    middlewares = [
        https_enforcement_middleware,
        security_headers_middleware,
        create_auth_middleware(key_manager)
    ]
    app = web.Application(middlewares=middlewares)
    app['key_manager'] = key_manager

    # Routes
    app.router.add_get('/health', health_handler)
    app.router.add_get('/auth/key-info', key_info_handler)

    # Admin UI routes
    setup_admin_routes(app)

    # Catch-all for proxying (must be last)
    app.router.add_route('*', '/{path_info:.*}', catch_all_handler)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    return app


def create_ssl_context():
    """Create SSL context for TLS if configured."""
    if not TLS_ENABLED:
        return None

    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(TLS_CERT_FILE, TLS_KEY_FILE)
    # Use modern TLS settings
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    return ssl_context


if __name__ == '__main__':
    app = create_app()
    ssl_context = create_ssl_context()

    if ssl_context:
        print(f"Starting HTTPS server on port {PORT}")
    else:
        print(f"Starting HTTP server on port {PORT} (TLS not configured)")

    web.run_app(app, host='0.0.0.0', port=PORT, ssl_context=ssl_context)
