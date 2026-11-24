"""
Authentication Proxy Server for Privatemode.

This server sits in front of the Privatemode proxy and provides:
- API key authentication
- Rate limiting
- Token usage tracking (metadata only, never content)
- Key rotation support via hot-reload
"""

import ssl
import time
import json
import asyncio
import contextlib
from collections import defaultdict
from aiohttp import web, ClientSession, ClientTimeout, ClientError
from yarl import URL
from key_manager import KeyManager
from admin import setup_admin_routes, load_settings, ADMIN_HANDLERS
from usage_tracker import get_tracker
from config import (
    API_KEYS_FILE, UPSTREAM_URL, PORT,
    DEFAULT_RATE_LIMIT_REQUESTS, DEFAULT_RATE_LIMIT_WINDOW,
    DEFAULT_KEY_RATE_LIMIT_REQUESTS,
    DEFAULT_IP_RATE_LIMIT_REQUESTS, DEFAULT_IP_RATE_LIMIT_WINDOW,
    TLS_ENABLED, TLS_CERT_FILE, TLS_KEY_FILE, FORCE_HTTPS
)
from utils import get_client_ip, is_https_request, has_dot_segment


def get_rate_limit_settings() -> dict:
    """Get current rate limit settings from settings file or defaults."""
    settings = load_settings()
    return {
        'rate_limit_requests': settings.get('rate_limit_requests', DEFAULT_RATE_LIMIT_REQUESTS),
        'rate_limit_window': settings.get('rate_limit_window', DEFAULT_RATE_LIMIT_WINDOW),
        'key_rate_limit_requests': settings.get('key_rate_limit_requests', DEFAULT_KEY_RATE_LIMIT_REQUESTS),
        'ip_rate_limit_requests': settings.get('ip_rate_limit_requests', DEFAULT_IP_RATE_LIMIT_REQUESTS),
        'ip_rate_limit_window': settings.get('ip_rate_limit_window', DEFAULT_IP_RATE_LIMIT_WINDOW),
    }

# Rate limiting storage: key_id -> list of request timestamps
rate_limit_store: dict[str, list[float]] = defaultdict(list)

# Global rate limiting storage (shared across ALL keys)
global_rate_limit_store: list[float] = []

# IP rate limiting storage
ip_rate_limit_store: dict[str, list[float]] = defaultdict(list)

# How often idle per-IP / per-key entries are swept out of the stores above
STORE_SWEEP_INTERVAL = 60
_last_sweep = {'ip': 0.0, 'key': 0.0}

# How often buffered usage totals are written to disk
USAGE_FLUSH_INTERVAL = 30

# Headers never forwarded in either direction (RFC 7230 hop-by-hop)
HOP_BY_HOP_HEADERS = frozenset({
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade',
})

# Client headers that must not reach the upstream: our own credentials, the
# admin cookie, client-network details, and headers aiohttp sets itself.
REQUEST_HEADERS_NOT_FORWARDED = HOP_BY_HOP_HEADERS | {
    'host', 'authorization', 'x-api-key', 'cookie',
    'forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-real-ip',
    'accept-encoding', 'content-length',
}

# Upstream headers that must not reach the client: the body is already
# decompressed and re-framed by aiohttp, and upstream identity/cookies are not ours.
RESPONSE_HEADERS_NOT_FORWARDED = HOP_BY_HOP_HEADERS | {
    'content-encoding', 'content-length', 'server', 'set-cookie',
}

# Above this size an unterminated SSE event is passed through without inspection
MAX_SSE_EVENT_BYTES = 1024 * 1024


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


def _sweep_idle_entries(store: dict[str, list[float]], window_start: float) -> None:
    """Delete entries whose timestamps have all expired, so the store cannot grow forever."""
    for key in [k for k, stamps in store.items() if not stamps or stamps[-1] <= window_start]:
        del store[key]


def _maybe_sweep(name: str, store: dict[str, list[float]], window_start: float, now: float) -> None:
    if now - _last_sweep[name] >= STORE_SWEEP_INTERVAL:
        _sweep_idle_entries(store, window_start)
        _last_sweep[name] = now


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
    Keys without a limit of their own get the default per-key limit, so a
    single key cannot exhaust the global ceiling for everyone else.
    """
    settings = get_rate_limit_settings()
    if limit is None:
        limit = settings['key_rate_limit_requests']
    window = settings['rate_limit_window']

    now = time.time()
    window_start = now - window
    _maybe_sweep('key', rate_limit_store, window_start, now)

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
    _maybe_sweep('ip', ip_rate_limit_store, window_start, now)

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


def parse_json_object(body: bytes) -> dict | None:
    """Parse a body as a JSON object; None for anything else (invalid JSON, lists, ...)."""
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def extract_model_from_request(body: bytes) -> str:
    """Extract model name from request body."""
    data = parse_json_object(body) if body else None
    model = data.get('model') if data else None
    return model if isinstance(model, str) and model else 'unknown'


def _usage_from_object(data: dict | None, usage: dict) -> dict:
    """Copy model and token counts from a parsed response object into `usage`."""
    if not data:
        return usage
    model = data.get('model')
    if isinstance(model, str) and model:
        usage['model'] = model
    usage_data = data.get('usage')
    if isinstance(usage_data, dict):
        for field in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
            value = usage_data.get(field)
            if isinstance(value, int) and value >= 0:
                usage[field] = value
        # Embeddings report only total_tokens; count them as prompt tokens
        if 'prompt_tokens' not in usage_data and isinstance(usage_data.get('total_tokens'), int):
            usage['prompt_tokens'] = usage['total_tokens']
    return usage


def _empty_usage() -> dict:
    return {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0, 'model': 'unknown'}


def extract_usage_from_response(response_body: bytes, endpoint: str) -> dict:
    """
    Extract token usage from response body.
    Only extracts usage metadata, never the actual content.
    """
    return _usage_from_object(parse_json_object(response_body) if response_body else None,
                              _empty_usage())


def _sse_data_object(event: bytes) -> dict | None:
    """Return the JSON object carried by an SSE event's `data:` line, if any."""
    for line in event.split(b'\n'):
        line = line.rstrip(b'\r')
        if line.startswith(b'data:'):
            payload = line[5:].strip()
            if payload and payload != b'[DONE]':
                return parse_json_object(payload)
    return None


def _is_usage_only_chunk(data: dict | None) -> bool:
    """The extra chunk produced by stream_options.include_usage: usage and no choices."""
    return bool(data) and isinstance(data.get('usage'), dict) and not data.get('choices')


def build_upstream_url(request: web.Request) -> URL:
    """
    Build the upstream URL from the request's RAW (still-encoded) path and query.

    Using the raw path with encoded=True means yarl does not decode or
    re-normalise it, so the upstream sees exactly the path that passed
    authentication (dot segments are rejected before this point).
    """
    base = URL(UPSTREAM_URL)
    return URL.build(
        scheme=base.scheme,
        host=base.raw_host,
        port=base.explicit_port,
        path=base.raw_path.rstrip('/') + request.rel_url.raw_path,
        query_string=request.rel_url.raw_query_string,
        encoded=True,
    )


def prepare_upstream_body(body: bytes, endpoint: str) -> tuple[bytes, bool, bool]:
    """
    Decide whether this is a streaming request and, if so, ask the upstream to
    report token usage in the stream so streaming calls are metered too.

    Returns (body_to_send, is_stream, usage_chunk_injected). When we inject the
    usage request, the extra usage-only chunk is stripped before it reaches the
    client, so clients that did not ask for it never see it.
    """
    data = parse_json_object(body) if body else None
    if not data or data.get('stream') is not True:
        return body, False, False
    if endpoint not in ('chat', 'completions'):
        return body, True, False
    options = data.get('stream_options')
    if options is None:
        options = {}
    if not isinstance(options, dict) or options.get('include_usage'):
        return body, True, False
    data['stream_options'] = {**options, 'include_usage': True}
    return json.dumps(data).encode(), True, True


def _record_usage(request: web.Request, usage: dict, request_model: str,
                  endpoint: str, audio_bytes: int) -> None:
    if 'key_id' not in request:
        return
    model = usage['model'] if usage['model'] != 'unknown' else request_model
    get_tracker().record_usage(
        key_id=request['key_id'],
        model=model,
        endpoint=endpoint,
        prompt_tokens=usage['prompt_tokens'],
        completion_tokens=usage['completion_tokens'],
        total_tokens=usage['total_tokens'],
        audio_bytes=audio_bytes,
    )


async def _relay_stream(request: web.Request, upstream_response, headers: dict,
                        strip_usage_chunk: bool) -> tuple[web.StreamResponse, dict]:
    """Relay an SSE stream event by event, reading token usage on the way."""
    response = web.StreamResponse(status=upstream_response.status, headers=headers)
    await response.prepare(request)
    usage = _empty_usage()
    pending = b''
    client_gone = False
    try:
        async for chunk in upstream_response.content.iter_any():
            pending += chunk
            *events, pending = pending.split(b'\n\n')
            out = []
            for event in events:
                data = _sse_data_object(event)
                _usage_from_object(data, usage)
                if strip_usage_chunk and _is_usage_only_chunk(data):
                    continue
                out.append(event + b'\n\n')
            if len(pending) > MAX_SSE_EVENT_BYTES:
                out.append(pending)
                pending = b''
            if out:
                await response.write(b''.join(out))
        if pending:
            _usage_from_object(_sse_data_object(pending), usage)
            await response.write(pending)
    except (ClientError, asyncio.TimeoutError) as e:
        # Headers are already sent, so the client just sees the stream end early.
        print(f"Upstream stream interrupted: {type(e).__name__}", flush=True)
    except ConnectionResetError:
        # The client went away; the tokens produced so far are still billed.
        client_gone = True
    if not client_gone:
        await response.write_eof()
    return response, usage


async def proxy_request(request: web.Request, session: ClientSession,
                        extra_headers: dict | None = None) -> web.StreamResponse:
    """Proxy the request to upstream Privatemode proxy."""
    upstream_url = build_upstream_url(request)

    # The Privatemode binary authenticates to Privatemode itself (--apiKey),
    # so neither the client's credentials nor ours are sent upstream.
    headers = {
        key: value for key, value in request.headers.items()
        if key.lower() not in REQUEST_HEADERS_NOT_FORWARDED
    }

    body = await request.read()
    endpoint = detect_endpoint_type(request.path)
    request_model = extract_model_from_request(body)
    audio_bytes = len(body) if endpoint == 'transcriptions' else 0
    body, is_stream, injected = prepare_upstream_body(body, endpoint)

    try:
        async with session.request(
            method=request.method,
            url=upstream_url,
            headers=headers,
            data=body,
            allow_redirects=False
        ) as upstream_response:
            response_headers = {
                key: value for key, value in upstream_response.headers.items()
                if key.lower() not in RESPONSE_HEADERS_NOT_FORWARDED
            }
            response_headers.update(extra_headers or {})

            if is_stream and upstream_response.status == 200:
                response, usage = await _relay_stream(
                    request, upstream_response, response_headers, injected)
                _record_usage(request, usage, request_model, endpoint, audio_bytes)
                return response

            response_body = await upstream_response.read()
            if upstream_response.status == 200:
                usage = extract_usage_from_response(response_body, endpoint)
                _record_usage(request, usage, request_model, endpoint, audio_bytes)

            return web.Response(
                status=upstream_response.status,
                headers=response_headers,
                body=response_body
            )

    except asyncio.TimeoutError:
        return web.json_response({'error': 'Upstream timeout'}, status=504)
    except ClientError as e:
        print(f"Proxy error: {type(e).__name__}", flush=True)
        return web.json_response({'error': 'Proxy error'}, status=502)


@web.middleware
async def https_enforcement_middleware(request: web.Request, handler):
    """Enforce HTTPS connections when FORCE_HTTPS is enabled."""
    if not FORCE_HTTPS:
        return await handler(request)

    # Allow health checks over HTTP for internal load balancer probes
    if request.path == '/health':
        return await handler(request)

    if not is_https_request(request):
        return web.json_response(
            {'error': 'HTTPS required. Please use a secure connection.'},
            status=403
        )

    return await handler(request)


@web.middleware
async def reject_dot_segments_middleware(request: web.Request, handler):
    """
    Reject paths containing '.' or '..' segments (literal or percent-encoded).

    Such paths mean different things to different components (the router sees
    them raw, an HTTP client normalises them), which is how a path can pass one
    check and reach a different resource. No legitimate API path needs them.
    """
    if has_dot_segment(request.path):
        return web.json_response({'error': 'Invalid path'}, status=400)
    return await handler(request)


async def add_security_headers(request: web.Request, response: web.StreamResponse) -> None:
    """Add security headers to every response, including streamed ones."""
    # Content Security Policy - restrictive for admin UI
    if request.path.startswith('/admin'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "object-src 'none'; "
            "base-uri 'none'; "
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

    # Do not advertise the server software and version
    response.headers.popall('Server', None)


def _rate_limited(error: str, limit: int, window: int) -> web.Response:
    return web.json_response(
        {'error': error},
        status=429,
        headers={
            'X-RateLimit-Limit': str(limit),
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': str(int(time.time()) + window)
        }
    )


def create_auth_middleware(key_manager: KeyManager):
    """Create authentication middleware."""

    @web.middleware
    async def auth_middleware(request: web.Request, handler):
        # Exemptions are decided by the route that actually matched, never by
        # a path prefix: a prefix check can be satisfied by paths that are
        # then routed (and proxied) somewhere else.
        route_handler = getattr(request.match_info, 'handler', None)
        if route_handler is health_handler:
            return await handler(request)

        # Check global IP rate limit first (also covers the admin UI)
        client_ip = get_client_ip(request)
        ip_allowed, ip_remaining, ip_limit, ip_window = check_ip_rate_limit(client_ip)
        if not ip_allowed:
            return _rate_limited('Global rate limit exceeded', ip_limit, ip_window)

        # Admin pages use their own session authentication
        if route_handler in ADMIN_HANDLERS:
            return await handler(request)

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
            return _rate_limited('Global rate limit exceeded', global_limit, global_window)

        # Check per-key rate limit (key's own limit, or the default per-key limit)
        key_allowed, key_remaining, key_limit = check_per_key_rate_limit(
            key_obj.key_id, key_obj.rate_limit)
        if not key_allowed:
            return _rate_limited('Per-key rate limit exceeded', key_limit, global_window)

        request['rate_limit_remaining'] = min(key_remaining, global_remaining)
        request['rate_limit_limit'] = key_limit
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


async def catch_all_handler(request: web.Request) -> web.StreamResponse:
    """Proxy all other requests to upstream."""
    rate_limit_headers = {}
    if 'rate_limit_remaining' in request:
        rate_limit_headers = {
            'X-RateLimit-Remaining': str(request['rate_limit_remaining']),
            'X-RateLimit-Limit': str(request['rate_limit_limit']),
        }
    return await proxy_request(request, request.app['client_session'], rate_limit_headers)


async def _flush_usage_periodically() -> None:
    """Write buffered usage totals to disk off the event loop."""
    while True:
        await asyncio.sleep(USAGE_FLUSH_INTERVAL)
        await get_tracker().flush_async()


async def client_session_ctx(app: web.Application):
    """Own the upstream client session and the usage flusher for the app's lifetime."""
    timeout = ClientTimeout(total=300)  # 5 minute timeout for LLM requests
    app['client_session'] = ClientSession(timeout=timeout)
    flusher = asyncio.create_task(_flush_usage_periodically())
    print(f"Auth proxy started, forwarding to {UPSTREAM_URL}", flush=True)
    yield
    flusher.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await flusher
    await app['client_session'].close()
    await get_tracker().flush_async()


def create_app() -> web.Application:
    """Create the application."""
    key_manager = KeyManager(API_KEYS_FILE)

    # Middleware order: HTTPS enforcement -> path validation -> auth
    middlewares = [
        https_enforcement_middleware,
        reject_dot_segments_middleware,
        create_auth_middleware(key_manager)
    ]
    app = web.Application(middlewares=middlewares)
    app['key_manager'] = key_manager
    app.on_response_prepare.append(add_security_headers)

    # Routes
    app.router.add_get('/health', health_handler)
    app.router.add_get('/auth/key-info', key_info_handler)

    # Admin UI routes
    setup_admin_routes(app)

    # Catch-all for proxying (must be last)
    app.router.add_route('*', '/{path_info:.*}', catch_all_handler)

    app.cleanup_ctx.append(client_session_ctx)

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
        print(f"Starting HTTPS server on port {PORT}", flush=True)
    else:
        print(f"Starting HTTP server on port {PORT} (TLS not configured)", flush=True)

    web.run_app(app, host='0.0.0.0', port=PORT, ssl_context=ssl_context)
