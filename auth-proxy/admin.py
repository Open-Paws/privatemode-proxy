"""
Admin UI for API Key Management.

Provides a simple web interface to:
- View all API keys
- Generate new keys
- Revoke/enable keys
- Delete keys
- View usage and spend by key

Protected by admin password.
"""

import os
import json
import time
import hashlib
import secrets
import base64
from collections import defaultdict
from html import escape
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from aiohttp import web
from cryptography.fernet import Fernet
from usage_tracker import get_tracker, get_time_range
from config import (
    API_KEYS_FILE, SETTINGS_FILE, ADMIN_PASSWORD, PRIVATEMODE_API_KEY, TRUST_PROXY,
    DEFAULT_RATE_LIMIT_REQUESTS, DEFAULT_RATE_LIMIT_WINDOW, DEFAULT_KEY_RATE_LIMIT_REQUESTS,
    DEFAULT_IP_RATE_LIMIT_REQUESTS, DEFAULT_IP_RATE_LIMIT_WINDOW
)
from utils import get_client_ip, cookies_must_be_secure

# Aliases for backwards compatibility
KEYS_FILE = API_KEYS_FILE

# Session store: token -> (created_at, ip)
_sessions: dict[str, tuple[float, str]] = {}
SESSION_TTL = 86400  # 24 hours

# Login attempt tracking: IP -> list of timestamps
_login_attempts: dict[str, list[float]] = defaultdict(list)
LOGIN_RATE_LIMIT = 5  # max attempts
LOGIN_RATE_WINDOW = 300  # 5 minute window
_last_login_sweep = 0.0

SESSION_COOKIE = 'admin_session'

# Login error codes shown on the login page. Only these fixed messages can
# appear there, so a crafted link cannot put arbitrary text on the official page.
LOGIN_ERRORS = {
    'invalid': 'Invalid password',
    'expired': 'Your form expired. Please try again.',
}


def log_admin_event(event: str, **fields) -> None:
    """
    Write an admin security event to stdout as one JSON line.

    Client IP addresses are deliberately not logged: who used the admin UI
    from where is itself sensitive for this endpoint.
    """
    record = {'security_event': event, 'time': int(time.time()), **fields}
    print(json.dumps(record, sort_keys=True), flush=True)


def create_session(ip: str) -> str:
    """Create a new session and return the token."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = (time.time(), ip)
    _cleanup_sessions()
    return token


def validate_session(token: str, ip: str) -> bool:
    """Validate a session token."""
    if not token or token not in _sessions:
        return False
    created_at, session_ip = _sessions[token]
    # Check expiry
    if time.time() - created_at > SESSION_TTL:
        del _sessions[token]
        return False
    # Validate IP matches the session's original IP
    if ip != session_ip:
        return False
    return True


def delete_session(token: str) -> None:
    """Delete a session."""
    _sessions.pop(token, None)


def _cleanup_sessions() -> None:
    """Remove expired sessions."""
    now = time.time()
    expired = [t for t, (created, _) in _sessions.items() if now - created > SESSION_TTL]
    for t in expired:
        del _sessions[t]


def get_default_settings() -> dict:
    """Return default settings with rate limits from config."""
    return {
        'rate_limit_requests': DEFAULT_RATE_LIMIT_REQUESTS,
        'rate_limit_window': DEFAULT_RATE_LIMIT_WINDOW,
        'key_rate_limit_requests': DEFAULT_KEY_RATE_LIMIT_REQUESTS,
        'ip_rate_limit_requests': DEFAULT_IP_RATE_LIMIT_REQUESTS,
        'ip_rate_limit_window': DEFAULT_IP_RATE_LIMIT_WINDOW,
    }


def load_settings() -> dict:
    """Load settings from file, with defaults."""
    defaults = get_default_settings()
    if not os.path.exists(SETTINGS_FILE):
        return defaults
    try:
        with open(SETTINGS_FILE) as f:
            saved = json.load(f)
        # Merge saved settings with defaults (saved takes precedence)
        return {**defaults, **saved}
    except (json.JSONDecodeError, IOError):
        return defaults


def save_settings(data: dict) -> None:
    """Save settings to file."""
    Path(SETTINGS_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_privatemode_key_status() -> tuple[str, str]:
    """Get status of Privatemode API key. Returns (status_text, css_class)."""
    if PRIVATEMODE_API_KEY:
        # Only show prefix to minimize exposure
        if PRIVATEMODE_API_KEY.startswith('pm_'):
            return "Configured (pm_****)", "status-active"
        return "Configured (****)", "status-active"
    return "Not configured", "status-revoked"

# Temporary storage for newly generated keys (in-memory, short-lived)
# Maps key_id -> (encrypted_key, timestamp)
_pending_keys: dict[str, tuple[str, float]] = {}
PENDING_KEY_TTL = 60  # seconds

# CSRF tokens: token -> (created_at, session token it is bound to, or None for
# the anonymous login form). Insertion order equals creation order, so the
# oldest tokens are always at the front.
_csrf_tokens: dict[str, tuple[float, str | None]] = {}
CSRF_TTL = 3600  # 1 hour
MAX_CSRF_TOKENS = 10_000  # cap so anonymous page loads cannot exhaust memory


PBKDF2_SALT = os.environ.get('PBKDF2_SALT', '').encode()
if len(PBKDF2_SALT) < 16:
    raise ValueError("PBKDF2_SALT environment variable must be at least 16 bytes")

# Cache the derived Fernet key at module level so the expensive PBKDF2
# computation only runs once (avoids blocking the async event loop on
# every encrypt/decrypt call).
_FERNET_KEY: bytes | None = None


def _get_fernet_key() -> bytes:
    """Derive a Fernet key from admin password using PBKDF2.

    Uses PBKDF2-HMAC-SHA256 with a configurable salt for key derivation.
    The key is computed once and cached to avoid blocking the async event loop.
    """
    global _FERNET_KEY
    if _FERNET_KEY is not None:
        return _FERNET_KEY
    # Use PBKDF2 with 600,000 iterations (OWASP recommended for HMAC-SHA256)
    key_material = hashlib.pbkdf2_hmac(
        'sha256',
        ADMIN_PASSWORD.encode(),
        PBKDF2_SALT,
        iterations=600_000,
        dklen=32  # Fernet requires 32 bytes
    )
    _FERNET_KEY = base64.urlsafe_b64encode(key_material)
    return _FERNET_KEY


# Derive the key once at import time so the expensive PBKDF2 computation
# happens during startup, not on the first request (which would block the
# async event loop).
_get_fernet_key()


def _encrypt_key_for_display(key: str) -> str:
    """Encrypt a key for temporary storage."""
    f = Fernet(_get_fernet_key())
    return f.encrypt(key.encode()).decode()


def _decrypt_key_for_display(encrypted: str) -> str:
    """Decrypt a temporarily stored key."""
    f = Fernet(_get_fernet_key())
    return f.decrypt(encrypted.encode()).decode()


def _cleanup_pending_keys():
    """Remove expired pending keys."""
    now = time.time()
    expired = [k for k, (_, ts) in _pending_keys.items() if now - ts > PENDING_KEY_TTL]
    for k in expired:
        del _pending_keys[k]


def generate_csrf_token(session_token: str | None = None) -> str:
    """Generate a new CSRF token bound to a session (None = the login form)."""
    _cleanup_csrf_tokens()
    while len(_csrf_tokens) >= MAX_CSRF_TOKENS:
        del _csrf_tokens[next(iter(_csrf_tokens))]
    token = secrets.token_urlsafe(32)
    _csrf_tokens[token] = (time.time(), session_token)
    return token


def validate_csrf_token(token: str, session_token: str | None = None) -> bool:
    """Validate and consume a CSRF token; it must belong to the same session."""
    if not token or token not in _csrf_tokens:
        return False
    created_at, bound_session = _csrf_tokens.pop(token)
    if bound_session != session_token:
        return False
    return time.time() - created_at < CSRF_TTL


def _cleanup_csrf_tokens() -> None:
    """Remove expired CSRF tokens (they are all at the front of the dict)."""
    now = time.time()
    while _csrf_tokens:
        oldest = next(iter(_csrf_tokens))
        if now - _csrf_tokens[oldest][0] <= CSRF_TTL:
            break
        del _csrf_tokens[oldest]


def _sweep_login_attempts(window_start: float, now: float) -> None:
    """Forget IPs with no recent failed logins, so the tracker cannot grow forever."""
    global _last_login_sweep
    if now - _last_login_sweep < LOGIN_RATE_WINDOW:
        return
    for ip in [ip for ip, stamps in _login_attempts.items()
               if not stamps or stamps[-1] <= window_start]:
        del _login_attempts[ip]
    _last_login_sweep = now


def check_login_rate_limit(ip: str, record_attempt: bool = False) -> bool:
    """Check if IP is rate limited. Returns True if allowed.

    Args:
        ip: The IP address to check
        record_attempt: If True, record this as a failed login attempt
    """
    now = time.time()
    window_start = now - LOGIN_RATE_WINDOW
    _sweep_login_attempts(window_start, now)
    # Clean old entries
    _login_attempts[ip] = [ts for ts in _login_attempts[ip] if ts > window_start]
    if len(_login_attempts[ip]) >= LOGIN_RATE_LIMIT:
        return False
    if record_attempt:
        _login_attempts[ip].append(now)
    return True


def check_admin_auth(request: web.Request) -> bool:
    """Check if request has valid admin authentication."""
    if not ADMIN_PASSWORD:
        return False

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False

    ip = get_client_ip(request)
    return validate_session(token, ip)


def session_token(request: web.Request) -> str | None:
    """The admin session token sent with this request, if any."""
    return request.cookies.get(SESSION_COOKIE)


async def read_admin_form(request: web.Request):
    """
    Authenticate an admin POST and check its session-bound CSRF token.

    Returns the parsed form data, or an HTTP response to send instead.
    """
    if not check_admin_auth(request):
        raise web.HTTPFound('/admin/login')
    data = await request.post()
    if not validate_csrf_token(data.get('csrf_token', ''), session_token(request)):
        return web.Response(text="Invalid or expired CSRF token", status=403)
    return data


def load_keys() -> dict:
    """Load keys from file."""
    if not os.path.exists(KEYS_FILE):
        return {"keys": []}
    with open(KEYS_FILE) as f:
        return json.load(f)


def save_keys(data: dict) -> None:
    """Save keys to file."""
    Path(KEYS_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(KEYS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def update_key_rate_limit(key_id: str, rate_limit: int | None) -> bool:
    """Update the rate limit for a specific key. Returns True if successful."""
    keys_data = load_keys()
    for key in keys_data['keys']:
        if key['key_id'] == key_id:
            if rate_limit is None:
                key.pop('rate_limit', None)
            else:
                key['rate_limit'] = rate_limit
            save_keys(keys_data)
            return True
    return False


def format_timestamp(ts: float | None) -> str:
    """Format timestamp for display."""
    if ts is None:
        return "Never"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def get_key_status(key: dict) -> tuple[str, str]:
    """Get status and CSS class for a key."""
    if not key.get('enabled', True):
        return "Revoked", "status-revoked"
    expires_at = key.get('expires_at')
    if expires_at and time.time() > expires_at:
        return "Expired", "status-expired"
    return "Active", "status-active"


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Open Paws AI Proxy</title>
    <link rel="icon" href="/admin/static/logo.png" type="image/png">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
            padding: 2rem;
        }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ margin-bottom: 2rem; color: #f8fafc; }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        .brand img {{
            height: 40px;
            width: 40px;
            filter: invert(1);
        }}
        .brand-text {{
            font-size: 1.25rem;
            font-weight: 600;
            color: #f8fafc;
        }}
        .brand-text span {{
            color: #f97316;
        }}

        .card {{
            background: #1e293b;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid #334155;
        }}

        .generate-form {{ display: flex; gap: 1rem; flex-wrap: wrap; align-items: end; }}
        .form-group {{ display: flex; flex-direction: column; gap: 0.5rem; }}
        .form-group label {{ font-size: 0.875rem; color: #94a3b8; }}
        .form-group input {{
            padding: 0.75rem 1rem;
            border-radius: 8px;
            border: 1px solid #475569;
            background: #0f172a;
            color: #e2e8f0;
            font-size: 1rem;
        }}
        .form-group input:focus {{ outline: none; border-color: #3b82f6; }}

        button {{
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            border: none;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .btn-primary {{ background: #3b82f6; color: white; }}
        .btn-primary:hover {{ background: #2563eb; }}
        .btn-danger {{ background: #dc2626; color: white; }}
        .btn-danger:hover {{ background: #b91c1c; }}
        .btn-secondary {{ background: #475569; color: white; }}
        .btn-secondary:hover {{ background: #64748b; }}
        .btn-small {{ padding: 0.5rem 1rem; font-size: 0.875rem; }}

        .new-key-display {{
            background: #022c22;
            border: 1px solid #059669;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
            display: none;
        }}
        .new-key-display.show {{ display: block; }}
        .new-key-display code {{
            background: #0f172a;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            display: block;
            margin: 0.5rem 0;
            font-family: 'Monaco', 'Consolas', monospace;
            word-break: break-all;
        }}

        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 1rem; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ color: #94a3b8; font-weight: 500; font-size: 0.875rem; }}

        .status-active {{ color: #22c55e; }}
        .status-revoked {{ color: #ef4444; }}
        .status-expired {{ color: #f59e0b; }}

        .actions {{ display: flex; gap: 0.5rem; }}

        .empty-state {{
            text-align: center;
            padding: 3rem;
            color: #64748b;
        }}

        .login-form {{
            max-width: 400px;
            margin: 4rem auto;
        }}
        .login-form input {{
            width: 100%;
            margin-bottom: 1rem;
        }}
        .login-form button {{ width: 100%; }}

        .error {{ color: #ef4444; margin-top: 0.5rem; }}
        .success {{ color: #22c55e; margin-top: 0.5rem; }}
        .warning {{ color: #f59e0b; margin-top: 0.5rem; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; }}
        .logout {{ color: #94a3b8; text-decoration: none; background: none; padding: 0; font-size: 1rem; }}
        .logout:hover {{ color: #e2e8f0; }}
        .logout-form {{ display: inline; }}

        .nav {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid #334155; }}
        .nav a {{ color: #94a3b8; text-decoration: none; padding: 0.5rem 1rem; border-radius: 6px; }}
        .nav a:hover {{ color: #e2e8f0; background: #1e293b; }}
        .nav a.active {{ color: #3b82f6; background: #1e3a5f; }}

        .info-box {{
            background: #172554;
            border: 1px solid #1e40af;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            font-size: 0.875rem;
            color: #93c5fd;
        }}
        .info-box strong {{ color: #bfdbfe; }}

        @media (max-width: 640px) {{
            .generate-form {{ flex-direction: column; }}
            .form-group {{ width: 100%; }}
            .actions {{ flex-direction: column; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
    <script src="/admin/static/admin.js"></script>
</body>
</html>
"""

LOGIN_CONTENT = """
<div class="login-form">
    <div class="card" style="text-align: center;">
        <div class="brand" style="justify-content: center; margin-bottom: 1rem;">
            <img src="/admin/static/logo.png" alt="Open Paws" style="height: 50px; width: 50px;">
        </div>
        <h2 style="color: #f8fafc; margin-bottom: 0.25rem; font-size: 1.25rem;">Open <span style="color: #f97316;">Paws</span> Privatemode AI Proxy</h2>
        <p style="color: #22c55e; font-size: 0.75rem; margin-bottom: 1.5rem; font-family: monospace;">
            Privatemode E2E Encrypted
        </p>
        <form method="POST" action="/admin/login">
            <input type="hidden" name="csrf_token" value="{csrf_token}">
            <div class="form-group" style="text-align: left;">
                <label>Password</label>
                <input type="password" name="password" required autofocus placeholder="Enter admin password">
            </div>
            {error}
            <button type="submit" class="btn-primary" style="margin-top: 1rem;">Sign In</button>
        </form>
    </div>
</div>
"""

DASHBOARD_CONTENT = """
<div class="header">
    <div class="brand">
        <img src="/admin/static/logo.png" alt="Open Paws">
        <div class="brand-text">Open <span>Paws</span> Privatemode AI Proxy</div>
    </div>
    <form method="POST" action="/admin/logout" class="logout-form"><input type="hidden" name="csrf_token" value="{csrf_token}"><button type="submit" class="logout">Logout</button></form>
</div>

<div class="nav">
    <a href="/admin" class="active">API Keys</a>
    <a href="/admin/settings">Settings</a>
    <a href="/admin/usage">Usage &amp; Costs</a>
    <a href="/admin/about">Documentation</a>
</div>

<div style="background: linear-gradient(135deg, #064e3b 0%, #022c22 100%); border: 1px solid #059669; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 1rem;">
    <div style="font-size: 1.5rem;">&#x1F512;</div>
    <div>
        <div style="color: #34d399; font-weight: 600; font-size: 0.875rem;">End-to-End Encrypted via Privatemode</div>
        <div style="color: #6ee7b7; font-size: 0.75rem;">All requests encrypted in TEE &bull; No logs &bull; Zero data retention</div>
    </div>
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">Generate API Key</h3>
    <form method="POST" action="/admin/keys/generate" class="generate-form">
        <input type="hidden" name="csrf_token" value="{csrf_token}">
        <div class="form-group" style="flex: 2;">
            <label>Label</label>
            <input type="text" name="description" placeholder="e.g., sam-dev, n8n-workflow, testing">
        </div>
        <div class="form-group" style="flex: 1;">
            <label>TTL (days)</label>
            <input type="number" name="expires_days" placeholder="∞">
        </div>
        <div class="form-group" style="flex: 1;">
            <label>Rate limit</label>
            <input type="number" name="rate_limit" placeholder="req/min">
        </div>
        <button type="submit" class="btn-primary">Generate</button>
    </form>

    <div id="newKey" class="new-key-display {show_new_key}">
        <strong style="color: #22c55e;">Key Generated</strong>
        <code>{new_key}</code>
        <p style="color: #94a3b8; font-size: 0.75rem; margin-top: 0.5rem;">Copy now - this won't be shown again</p>
        <button type="button" data-copy="{new_key}" class="btn-secondary btn-small" style="margin-top: 0.5rem;">Copy</button>
    </div>
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">Active Keys</h3>
    {keys_table}
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">How to Use This Proxy</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1.5rem; line-height: 1.6;">
        This proxy is fully compatible with the OpenAI API. If you're already using OpenAI in your code,
        you just need to change two things: point to this server instead of OpenAI, and use an API key from above.
    </p>

    <div style="margin-bottom: 2rem;">
        <div style="color: #3b82f6; font-size: 0.875rem; font-weight: 600; margin-bottom: 0.75rem;">Python Example</div>
        <p style="color: #64748b; font-size: 0.8rem; margin-bottom: 0.75rem;">Install the OpenAI package if you haven't: <code style="background: #0f172a; padding: 0.125rem 0.5rem; border-radius: 4px;">pip install openai</code></p>
        <pre style="background: #0f172a; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.8rem;"><code style="color: #e2e8f0;">from openai import OpenAI

# Create a client pointing to this proxy
client = OpenAI(
    base_url="{base_url}/v1",  # This proxy URL
    api_key="YOUR_API_KEY_FROM_ABOVE"  # Generate one above
)

# Make a request - works exactly like the OpenAI API
response = client.chat.completions.create(
    model="gpt-oss-120b",
    messages=[
        {{"role": "user", "content": "Hello, how are you?"}}
    ]
)

print(response.choices[0].message.content)</code></pre>
    </div>

    <div style="margin-bottom: 2rem;">
        <div style="color: #22c55e; font-size: 0.875rem; font-weight: 600; margin-bottom: 0.75rem;">cURL Example</div>
        <p style="color: #64748b; font-size: 0.8rem; margin-bottom: 0.75rem;">For testing from the command line or integrating with other tools:</p>
        <pre style="background: #0f172a; padding: 1rem; border-radius: 8px; overflow-x: auto; font-size: 0.8rem;"><code style="color: #e2e8f0;">curl {base_url}/v1/chat/completions \\
  -H "Authorization: Bearer YOUR_API_KEY_FROM_ABOVE" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "model": "gpt-oss-120b",
    "messages": [{{"role": "user", "content": "Hello!"}}]
  }}'</code></pre>
    </div>

    <div style="background: #0f172a; border-radius: 8px; padding: 1.25rem;">
        <div style="color: #f8fafc; font-size: 0.875rem; font-weight: 600; margin-bottom: 1rem;">Available Models</div>
        <div style="display: grid; gap: 0.75rem; font-size: 0.875rem;">
            <div>
                <span style="color: #94a3b8;">Chat Completion Models:</span>
                <span style="color: #e2e8f0; font-family: monospace; margin-left: 0.5rem;">gpt-oss-120b</span>,
                <span style="color: #e2e8f0; font-family: monospace;">gemma-3-27b</span>,
                <span style="color: #e2e8f0; font-family: monospace;">qwen3-coder-30b-a3b</span>
            </div>
            <div>
                <span style="color: #94a3b8;">Text Embeddings:</span>
                <span style="color: #e2e8f0; font-family: monospace; margin-left: 0.5rem;">qwen3-embedding-4b</span>
                <span style="color: #64748b; margin-left: 0.5rem;">(for vector search, RAG, etc.)</span>
            </div>
            <div>
                <span style="color: #94a3b8;">Speech to Text:</span>
                <span style="color: #e2e8f0; font-family: monospace; margin-left: 0.5rem;">whisper-large-v3</span>
                <span style="color: #64748b; margin-left: 0.5rem;">(audio transcription)</span>
            </div>
        </div>
    </div>
</div>
"""

KEYS_TABLE = """
<table>
    <thead>
        <tr>
            <th>Key ID</th>
            <th>Description</th>
            <th>Status</th>
            <th>Rate Limit</th>
            <th>Created</th>
            <th>Expires</th>
            <th>Actions</th>
        </tr>
    </thead>
    <tbody>
        {rows}
    </tbody>
</table>
"""

KEY_ROW = """
<tr>
    <td><code>{key_id}</code></td>
    <td>{description}</td>
    <td class="{status_class}">{status}</td>
    <td>{rate_limit_display}</td>
    <td>{created}</td>
    <td>{expires}</td>
    <td class="actions">
        {actions}
    </td>
</tr>
"""


async def admin_login_page(request: web.Request) -> web.Response:
    """Show login page."""
    if not ADMIN_PASSWORD:
        return web.Response(
            text="Admin UI disabled. Set ADMIN_PASSWORD environment variable to enable.",
            status=403
        )

    if check_admin_auth(request):
        raise web.HTTPFound('/admin')

    # Only fixed messages: the query value is a code, never displayed text
    error = LOGIN_ERRORS.get(request.query.get('error', ''))
    error_html = f'<p class="error">{escape(error)}</p>' if error else ''

    csrf_token = generate_csrf_token()
    html = HTML_TEMPLATE.format(
        content=LOGIN_CONTENT.format(error=error_html, csrf_token=csrf_token)
    )
    return web.Response(text=html, content_type='text/html')


async def admin_login_post(request: web.Request) -> web.Response:
    """Handle login POST."""
    if not ADMIN_PASSWORD:
        raise web.HTTPForbidden()

    client_ip = get_client_ip(request)

    # Check rate limit BEFORE password validation
    if not check_login_rate_limit(client_ip):
        log_admin_event('admin_login_rate_limited')
        return web.Response(
            text="Too many login attempts. Please try again later.",
            status=429
        )

    data = await request.post()
    csrf_token = data.get('csrf_token', '')
    password = data.get('password', '')

    # Validate CSRF token. A bad token counts as a failed attempt, so the
    # limiter also stops floods of forged or replayed login posts.
    if not validate_csrf_token(csrf_token):
        check_login_rate_limit(client_ip, record_attempt=True)
        raise web.HTTPFound('/admin/login?error=expired')

    if secrets.compare_digest(password, ADMIN_PASSWORD):
        # Create a new random session token
        token = create_session(client_ip)
        log_admin_event('admin_login_success')
        response = web.HTTPFound('/admin')
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=86400,  # 24 hours
            path='/admin',
            httponly=True,
            samesite='Strict',
            # Secure whenever the deployment serves HTTPS, including when TLS
            # terminates in this app (no X-Forwarded-Proto header then).
            secure=cookies_must_be_secure(request)
        )
        raise response

    # Record failed login attempt
    check_login_rate_limit(client_ip, record_attempt=True)
    log_admin_event('admin_login_failure')
    raise web.HTTPFound('/admin/login?error=invalid')


async def admin_logout(request: web.Request) -> web.Response:
    """Handle logout (POST with a CSRF token, so other sites cannot trigger it)."""
    data = await read_admin_form(request)
    if isinstance(data, web.Response):
        return data

    delete_session(session_token(request))
    log_admin_event('admin_logout')
    response = web.HTTPFound('/admin/login')
    response.del_cookie(SESSION_COOKIE, path='/admin')
    raise response


async def admin_dashboard(request: web.Request) -> web.Response:
    """Show admin dashboard."""
    if not ADMIN_PASSWORD:
        return web.Response(
            text="Admin UI disabled. Set ADMIN_PASSWORD environment variable to enable.",
            status=403
        )

    if not check_admin_auth(request):
        raise web.HTTPFound('/admin/login')

    # Check for newly generated key to display (one-time retrieval)
    new_key = ''
    show_new_key = ''
    show_key_id = request.query.get('show_key', '')
    if show_key_id and show_key_id in _pending_keys:
        encrypted_key, timestamp = _pending_keys.pop(show_key_id)  # Remove after retrieval
        if time.time() - timestamp < PENDING_KEY_TTL:
            new_key = _decrypt_key_for_display(encrypted_key)
            show_new_key = 'show'

    # Load keys
    data = load_keys()

    # Generate CSRF token for forms (bound to this admin session)
    csrf_token = generate_csrf_token(session_token(request))

    # Build keys table
    if not data['keys']:
        keys_table = '<div class="empty-state">No API keys configured. Generate one above.</div>'
    else:
        rows = []
        for key in data['keys']:
            status, status_class = get_key_status(key)
            # key_id goes into a URL path inside an HTML attribute
            key_path = escape(quote(str(key['key_id']), safe=''))

            if key.get('enabled', True):
                actions = f'''
                    <form method="POST" action="/admin/keys/{key_path}/revoke" style="display:inline;">
                        <input type="hidden" name="csrf_token" value="{csrf_token}">
                        <button type="submit" class="btn-danger btn-small">Revoke</button>
                    </form>
                '''
            else:
                actions = f'''
                    <form method="POST" action="/admin/keys/{key_path}/enable" style="display:inline;">
                        <input type="hidden" name="csrf_token" value="{csrf_token}">
                        <button type="submit" class="btn-secondary btn-small">Enable</button>
                    </form>
                '''

            actions += f'''
                <form method="POST" action="/admin/keys/{key_path}/delete" style="display:inline;"
                      data-confirm="Delete this key permanently?">
                    <input type="hidden" name="csrf_token" value="{csrf_token}">
                    <button type="submit" class="btn-secondary btn-small">Delete</button>
                </form>
            '''

            # Format rate limit display with inline edit form
            key_rate_limit = key.get('rate_limit')
            if key_rate_limit:
                rate_limit_display = f'''
                    <form method="POST" action="/admin/keys/{key_path}/rate-limit" style="display: flex; gap: 0.25rem; align-items: center;">
                        <input type="hidden" name="csrf_token" value="{csrf_token}">
                        <input type="number" name="rate_limit" value="{key_rate_limit}" style="width: 70px; padding: 0.25rem; font-size: 0.8rem; background: #0f172a; border: 1px solid #475569; border-radius: 4px; color: #e2e8f0;">
                        <button type="submit" class="btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">Set</button>
                        <button type="submit" name="clear" value="1" class="btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" title="Use the default per-key limit">×</button>
                    </form>
                '''
            else:
                rate_limit_display = f'''
                    <form method="POST" action="/admin/keys/{key_path}/rate-limit" style="display: flex; gap: 0.25rem; align-items: center;">
                        <input type="hidden" name="csrf_token" value="{csrf_token}">
                        <input type="number" name="rate_limit" placeholder="default" style="width: 70px; padding: 0.25rem; font-size: 0.8rem; background: #0f172a; border: 1px solid #475569; border-radius: 4px; color: #64748b;">
                        <button type="submit" class="btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">Set</button>
                    </form>
                '''

            rows.append(KEY_ROW.format(
                key_id=escape(key['key_id']),
                description=escape(key.get('description', '-')),
                status=status,
                status_class=status_class,
                rate_limit_display=rate_limit_display,
                created=format_timestamp(key.get('created_at')),
                expires=format_timestamp(key.get('expires_at')),
                actions=actions
            ))

        keys_table = KEYS_TABLE.format(rows=''.join(rows))

    # Determine base URL for usage examples
    scheme, host = request.scheme, request.host
    if TRUST_PROXY:
        scheme = request.headers.get('X-Forwarded-Proto', scheme)
        host = request.headers.get('X-Forwarded-Host', host)
    base_url = escape(f"{scheme}://{host}")

    content = DASHBOARD_CONTENT.format(
        keys_table=keys_table,
        new_key=escape(new_key),
        show_new_key=show_new_key,
        base_url=base_url,
        csrf_token=csrf_token
    )

    html = HTML_TEMPLATE.format(content=content)
    return web.Response(text=html, content_type='text/html')


def positive_int(value) -> int | None:
    """Parse a form value as a whole number greater than zero; None otherwise."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


async def admin_generate_key(request: web.Request) -> web.Response:
    """Generate a new API key."""
    data = await read_admin_form(request)
    if isinstance(data, web.Response):
        return data

    description = data.get('description', '')
    expires_days = positive_int(data.get('expires_days'))
    rate_limit = positive_int(data.get('rate_limit'))

    # Generate key
    new_key = f"pm_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(new_key.encode()).hexdigest()
    key_id = f"key_{secrets.token_hex(4)}"

    entry = {
        'key_id': key_id,
        'key_hash': key_hash,
        'created_at': time.time(),
        'description': description,
        'enabled': True
    }

    if expires_days:
        entry['expires_at'] = time.time() + (expires_days * 86400)

    if rate_limit:
        entry['rate_limit'] = rate_limit

    # Save
    keys_data = load_keys()
    keys_data['keys'].append(entry)
    save_keys(keys_data)
    log_admin_event('api_key_generated', key_id=key_id)

    # Store encrypted key temporarily for one-time display
    _cleanup_pending_keys()
    _pending_keys[key_id] = (_encrypt_key_for_display(new_key), time.time())

    # Redirect with just the key_id (not the actual key)
    raise web.HTTPFound(f'/admin?show_key={key_id}')


async def admin_revoke_key(request: web.Request) -> web.Response:
    """Revoke an API key."""
    data = await read_admin_form(request)
    if isinstance(data, web.Response):
        return data

    key_id = request.match_info['key_id']

    keys_data = load_keys()
    for key in keys_data['keys']:
        if key['key_id'] == key_id:
            key['enabled'] = False
            key['revoked_at'] = time.time()
            break

    save_keys(keys_data)
    log_admin_event('api_key_revoked', key_id=key_id)
    raise web.HTTPFound('/admin')


async def admin_enable_key(request: web.Request) -> web.Response:
    """Re-enable an API key."""
    data = await read_admin_form(request)
    if isinstance(data, web.Response):
        return data

    key_id = request.match_info['key_id']

    keys_data = load_keys()
    for key in keys_data['keys']:
        if key['key_id'] == key_id:
            key['enabled'] = True
            if 'revoked_at' in key:
                del key['revoked_at']
            break

    save_keys(keys_data)
    log_admin_event('api_key_enabled', key_id=key_id)
    raise web.HTTPFound('/admin')


async def admin_delete_key(request: web.Request) -> web.Response:
    """Delete an API key permanently."""
    data = await read_admin_form(request)
    if isinstance(data, web.Response):
        return data

    key_id = request.match_info['key_id']

    keys_data = load_keys()
    keys_data['keys'] = [k for k in keys_data['keys'] if k['key_id'] != key_id]
    save_keys(keys_data)
    log_admin_event('api_key_deleted', key_id=key_id)

    raise web.HTTPFound('/admin')


async def admin_update_key_rate_limit(request: web.Request) -> web.Response:
    """Update rate limit for a specific API key."""
    data = await read_admin_form(request)
    if isinstance(data, web.Response):
        return data

    key_id = request.match_info['key_id']

    # Check if clearing the rate limit
    if data.get('clear'):
        if update_key_rate_limit(key_id, None):
            log_admin_event('api_key_rate_limit_cleared', key_id=key_id)
    else:
        rate_limit = positive_int(data.get('rate_limit'))
        if rate_limit and update_key_rate_limit(key_id, rate_limit):
            log_admin_event('api_key_rate_limit_set', key_id=key_id, rate_limit=rate_limit)

    raise web.HTTPFound('/admin')


RATE_LIMIT_SETTING_FIELDS = (
    'rate_limit_requests', 'rate_limit_window', 'key_rate_limit_requests',
    'ip_rate_limit_requests', 'ip_rate_limit_window',
)


async def admin_save_rate_limits(request: web.Request) -> web.Response:
    """Save global rate limit settings."""
    data = await read_admin_form(request)
    if isinstance(data, web.Response):
        return data

    # Load existing settings
    settings = load_settings()

    # Only whole numbers above zero are accepted; anything else keeps the old value
    changed = {}
    for field in RATE_LIMIT_SETTING_FIELDS:
        value = positive_int(data.get(field))
        if value is not None:
            settings[field] = value
            changed[field] = value

    save_settings(settings)
    log_admin_event('rate_limit_settings_saved', **changed)

    raise web.HTTPFound('/admin/settings?success=rate_limits')


USAGE_CONTENT = """
<div class="header">
    <div class="brand">
        <img src="/admin/static/logo.png" alt="Open Paws">
        <div class="brand-text">Open <span>Paws</span> Privatemode AI Proxy</div>
    </div>
    <form method="POST" action="/admin/logout" class="logout-form"><input type="hidden" name="csrf_token" value="{csrf_token}"><button type="submit" class="logout">Logout</button></form>
</div>

<div class="nav">
    <a href="/admin">API Keys</a>
    <a href="/admin/settings">Settings</a>
    <a href="/admin/usage" class="active">Usage &amp; Costs</a>
    <a href="/admin/about">Documentation</a>
</div>

<div class="card" style="padding: 1rem;">
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem;">Select a time period to view usage statistics:</p>
    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
        <a href="/admin/usage?period=today" class="btn-secondary btn-small {active_today}">Today</a>
        <a href="/admin/usage?period=week" class="btn-secondary btn-small {active_week}">Last 7 Days</a>
        <a href="/admin/usage?period=month" class="btn-secondary btn-small {active_month}">Last 30 Days</a>
        <a href="/admin/usage?period=year" class="btn-secondary btn-small {active_year}">Last Year</a>
        <a href="/admin/usage?period=all" class="btn-secondary btn-small {active_all}">All Time</a>
    </div>
</div>

<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem;">
    <div class="card" style="text-align: center;">
        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Total Spend</div>
        <div style="color: #22c55e; font-size: 1.75rem; font-weight: 700; font-family: monospace;">€{total_cost:.2f}</div>
    </div>
    <div class="card" style="text-align: center;">
        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">Tokens Used</div>
        <div style="color: #e2e8f0; font-size: 1.75rem; font-weight: 700; font-family: monospace;">{total_tokens:,}</div>
    </div>
    <div class="card" style="text-align: center;">
        <div style="color: #64748b; font-size: 0.875rem; margin-bottom: 0.25rem;">API Requests</div>
        <div style="color: #e2e8f0; font-size: 1.75rem; font-weight: 700; font-family: monospace;">{total_requests:,}</div>
    </div>
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">Usage Breakdown by API Key</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem;">
        See which API keys are using the most resources.
    </p>
    {usage_by_key_table}
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">Usage Breakdown by Model</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem;">
        See which AI models are being used the most.
    </p>
    {usage_by_model_table}
</div>
"""

USAGE_BY_KEY_TABLE = """
<table>
    <thead>
        <tr>
            <th>Key</th>
            <th style="text-align: right;">Tokens</th>
            <th style="text-align: right;">Requests</th>
            <th style="text-align: right;">Spend (EUR)</th>
        </tr>
    </thead>
    <tbody>
        {rows}
    </tbody>
</table>
"""

USAGE_BY_KEY_ROW = """
<tr>
    <td>{description}</td>
    <td style="text-align: right;">{tokens:,}</td>
    <td style="text-align: right;">{requests:,}</td>
    <td style="text-align: right; color: #22c55e;">€{cost:.4f}</td>
</tr>
"""

USAGE_BY_MODEL_TABLE = """
<table>
    <thead>
        <tr>
            <th>Model</th>
            <th style="text-align: right;">Tokens</th>
            <th style="text-align: right;">Requests</th>
            <th style="text-align: right;">Spend (EUR)</th>
        </tr>
    </thead>
    <tbody>
        {rows}
    </tbody>
</table>
"""

USAGE_BY_MODEL_ROW = """
<tr>
    <td><code>{model}</code></td>
    <td style="text-align: right;">{tokens:,}</td>
    <td style="text-align: right;">{requests:,}</td>
    <td style="text-align: right; color: #22c55e;">€{cost:.4f}</td>
</tr>
"""

SETTINGS_CONTENT = """
<div class="header">
    <div class="brand">
        <img src="/admin/static/logo.png" alt="Open Paws">
        <div class="brand-text">Open <span>Paws</span> Privatemode AI Proxy</div>
    </div>
    <form method="POST" action="/admin/logout" class="logout-form"><input type="hidden" name="csrf_token" value="{csrf_token}"><button type="submit" class="logout">Logout</button></form>
</div>

<div class="nav">
    <a href="/admin">API Keys</a>
    <a href="/admin/settings" class="active">Settings</a>
    <a href="/admin/usage">Usage &amp; Costs</a>
    <a href="/admin/about">Documentation</a>
</div>

{success_message}

<div class="card">
    <h3 style="margin-bottom: 1rem;">Privatemode Connection Status</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.6;">
        This proxy connects to Privatemode's encrypted AI infrastructure.
        The connection status below shows whether your Privatemode API key is configured.
    </p>
    <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
        <div style="width: 12px; height: 12px; border-radius: 50%; background: {pm_dot_color};"></div>
        <span style="font-size: 1rem; color: #f8fafc;">{pm_key_status}</span>
    </div>
    {pm_key_message}
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">Rate Limit Settings</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.6;">
        The global rate limit is a ceiling shared across ALL API keys. Each key is also limited on its own:
        keys without a limit of their own get the default per-key limit, so one key cannot use up the shared ceiling.
        Per-key limits set on the API Keys page override the default for that key.
    </p>
    <form method="POST" action="/admin/settings/rate-limits" style="display: grid; gap: 1rem;">
        <input type="hidden" name="csrf_token" value="{csrf_token}">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
                <label>Global Rate Limit (total requests across all keys)</label>
                <input type="number" name="rate_limit_requests" value="{rate_limit_requests}" min="1" placeholder="100">
            </div>
            <div class="form-group">
                <label>Rate Limit Window (seconds)</label>
                <input type="number" name="rate_limit_window" value="{rate_limit_window}" min="1" placeholder="60">
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
                <label>Default Per-Key Limit (requests per key per window)</label>
                <input type="number" name="key_rate_limit_requests" value="{key_rate_limit_requests}" min="1" placeholder="60">
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
                <label>IP Rate Limit (requests per IP address)</label>
                <input type="number" name="ip_rate_limit_requests" value="{ip_rate_limit_requests}" min="1" placeholder="1000">
            </div>
            <div class="form-group">
                <label>IP Rate Limit Window (seconds)</label>
                <input type="number" name="ip_rate_limit_window" value="{ip_rate_limit_window}" min="1" placeholder="60">
            </div>
        </div>
        <div style="display: flex; gap: 1rem; align-items: center;">
            <button type="submit" class="btn-primary">Save Rate Limits</button>
            <span style="color: #64748b; font-size: 0.8rem;">Changes take effect immediately (no restart needed)</span>
        </div>
    </form>
</div>

"""


async def admin_settings(request: web.Request) -> web.Response:
    """Show settings page."""
    if not ADMIN_PASSWORD:
        return web.Response(
            text="Admin UI disabled. Set ADMIN_PASSWORD environment variable to enable.",
            status=403
        )

    if not check_admin_auth(request):
        raise web.HTTPFound('/admin/login')

    # Check for success message
    success = request.query.get('success', '')
    success_message = ''
    if success == 'rate_limits':
        success_message = '<div class="info-box" style="background: #022c22; border-color: #059669; color: #6ee7b7;">Rate limit settings saved successfully.</div>'

    # Get Privatemode key status
    pm_key_status, pm_key_status_class = get_privatemode_key_status()

    # Build message and dot color based on key status
    if PRIVATEMODE_API_KEY:
        pm_key_message = '<p style="color: #6ee7b7; font-size: 0.75rem;">E2E encryption active</p>'
        pm_dot_color = '#22c55e'
    else:
        pm_key_message = '<p style="color: #f87171; font-size: 0.75rem;">Not configured - set PRIVATEMODE_API_KEY</p>'
        pm_dot_color = '#ef4444'

    # Load current rate limit settings
    settings = load_settings()
    csrf_token = generate_csrf_token(session_token(request))

    content = SETTINGS_CONTENT.format(
        pm_key_status=pm_key_status,
        pm_key_status_class=pm_key_status_class,
        pm_key_message=pm_key_message,
        pm_dot_color=pm_dot_color,
        csrf_token=csrf_token,
        success_message=success_message,
        rate_limit_requests=settings.get('rate_limit_requests', 100),
        rate_limit_window=settings.get('rate_limit_window', 60),
        key_rate_limit_requests=settings.get('key_rate_limit_requests', DEFAULT_KEY_RATE_LIMIT_REQUESTS),
        ip_rate_limit_requests=settings.get('ip_rate_limit_requests', 1000),
        ip_rate_limit_window=settings.get('ip_rate_limit_window', 60),
    )

    html = HTML_TEMPLATE.format(content=content)
    return web.Response(text=html, content_type='text/html')


async def admin_usage(request: web.Request) -> web.Response:
    """Show usage dashboard."""
    if not ADMIN_PASSWORD:
        return web.Response(
            text="Admin UI disabled. Set ADMIN_PASSWORD environment variable to enable.",
            status=403
        )

    if not check_admin_auth(request):
        raise web.HTTPFound('/admin/login')

    # Get time period from query params
    period = request.query.get('period', 'month')
    start_time, end_time = get_time_range(period)

    # Period labels and active states
    period_labels = {
        'today': 'Today',
        'week': 'Last 7 Days',
        'month': 'Last 30 Days',
        'year': 'Last Year',
        'all': 'All Time'
    }
    period_label = period_labels.get(period, 'Last 30 Days')

    # Active button states
    active_states = {
        'active_today': 'btn-primary' if period == 'today' else '',
        'active_week': 'btn-primary' if period == 'week' else '',
        'active_month': 'btn-primary' if period == 'month' else '',
        'active_year': 'btn-primary' if period == 'year' else '',
        'active_all': 'btn-primary' if period == 'all' else ''
    }

    tracker = get_tracker()

    # Get overall summary
    summary = tracker.get_usage_summary(start_time=start_time, end_time=end_time)

    # Get usage by key
    usage_by_key = tracker.get_usage_by_key(start_time=start_time, end_time=end_time)

    # Load keys to get descriptions
    keys_data = load_keys()
    key_descriptions = {k['key_id']: k.get('description', '-') for k in keys_data.get('keys', [])}

    # Build usage by key table
    if not usage_by_key:
        usage_by_key_table = '<div class="empty-state">No usage data for this period.</div>'
    else:
        rows = []
        # Sort by cost descending
        sorted_keys = sorted(usage_by_key.items(), key=lambda x: x[1]['cost_eur'], reverse=True)
        for key_id, data in sorted_keys:
            rows.append(USAGE_BY_KEY_ROW.format(
                description=escape(key_descriptions.get(key_id, 'Unknown Key')),
                tokens=data['tokens'],
                requests=data['requests'],
                cost=data['cost_eur']
            ))
        usage_by_key_table = USAGE_BY_KEY_TABLE.format(rows=''.join(rows))

    # Build usage by model table
    if not summary['by_model']:
        usage_by_model_table = '<div class="empty-state">No usage data for this period.</div>'
    else:
        rows = []
        # Sort by cost descending
        sorted_models = sorted(summary['by_model'].items(), key=lambda x: x[1]['cost'], reverse=True)
        for model, data in sorted_models:
            rows.append(USAGE_BY_MODEL_ROW.format(
                model=escape(model),
                tokens=data['tokens'],
                requests=data['requests'],
                cost=data['cost']
            ))
        usage_by_model_table = USAGE_BY_MODEL_TABLE.format(rows=''.join(rows))

    content = USAGE_CONTENT.format(
        csrf_token=generate_csrf_token(session_token(request)),
        period_label=period_label,
        total_cost=summary['total_cost_eur'],
        total_tokens=summary['total_tokens'],
        total_requests=summary['requests'],
        usage_by_key_table=usage_by_key_table,
        usage_by_model_table=usage_by_model_table,
        **active_states
    )

    html = HTML_TEMPLATE.format(content=content)
    return web.Response(text=html, content_type='text/html')


ABOUT_CONTENT = """
<div class="header">
    <div class="brand">
        <img src="/admin/static/logo.png" alt="Open Paws">
        <div class="brand-text">Open <span>Paws</span> Privatemode AI Proxy</div>
    </div>
    <form method="POST" action="/admin/logout" class="logout-form"><input type="hidden" name="csrf_token" value="{csrf_token}"><button type="submit" class="logout">Logout</button></form>
</div>

<div class="nav">
    <a href="/admin">API Keys</a>
    <a href="/admin/settings">Settings</a>
    <a href="/admin/usage">Usage &amp; Costs</a>
    <a href="/admin/about" class="active">Documentation</a>
</div>

<div style="background: linear-gradient(135deg, #064e3b 0%, #022c22 100%); border: 1px solid #059669; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem;">
    <h2 style="color: #34d399; font-size: 1.25rem; margin-bottom: 1rem;">What is End-to-End Encrypted AI?</h2>
    <p style="color: #e2e8f0; font-size: 0.9375rem; line-height: 1.7; margin-bottom: 1rem;">
        When you send a prompt through this proxy, it goes to <strong style="color: #34d399;">Privatemode</strong>'s
        servers which run inside a special secure environment called a
        <strong>Trusted Execution Environment (TEE)</strong>.
    </p>
    <p style="color: #94a3b8; font-size: 0.875rem; line-height: 1.7; margin-bottom: 1rem;">
        Think of a TEE like a locked box that even the server owner can't open.
        Your prompts and the AI's responses are encrypted inside this box -
        <strong style="color: #f8fafc;">nobody can see your data</strong>, not even Privatemode themselves.
    </p>
    <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 0.875rem; color: #a7f3d0; margin-top: 1rem;">
        <span>&#x2713; Your prompts are never logged</span>
        <span>&#x2713; Your data is never used for training</span>
        <span>&#x2713; Fully GDPR compliant</span>
    </div>
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">How Requests Flow Through the System</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.6;">
        Here's what happens when your application makes an API request:
    </p>
    <div style="background: #0f172a; border-radius: 8px; padding: 1.25rem; line-height: 2;">
        <div style="font-size: 0.9375rem;">
            <strong style="color: #e2e8f0;">1.</strong>
            <span style="color: #94a3b8;">Your app sends a request to</span>
            <span style="color: #f97316;">this proxy</span>
        </div>
        <div style="font-size: 0.9375rem;">
            <strong style="color: #e2e8f0;">2.</strong>
            <span style="color: #94a3b8;">The proxy validates your API key and checks rate limits</span>
        </div>
        <div style="font-size: 0.9375rem;">
            <strong style="color: #e2e8f0;">3.</strong>
            <span style="color: #94a3b8;">The request is forwarded to</span>
            <span style="color: #22c55e;">Privatemode's encrypted servers</span>
        </div>
        <div style="font-size: 0.9375rem;">
            <strong style="color: #e2e8f0;">4.</strong>
            <span style="color: #94a3b8;">The AI model processes your request inside the secure TEE</span>
        </div>
        <div style="font-size: 0.9375rem;">
            <strong style="color: #e2e8f0;">5.</strong>
            <span style="color: #94a3b8;">The response comes back through the proxy to your app</span>
        </div>
    </div>
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">How We Track Usage Without Breaking Privacy</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.6;">
        You might wonder: if everything is encrypted, how do we track token usage for billing?
    </p>
    <p style="color: #e2e8f0; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.6;">
        The answer is that <strong>we only read the usage metadata</strong> from the response -
        specifically the <code style="background: #0f172a; padding: 0.125rem 0.5rem; border-radius: 4px;">usage</code>
        field that contains token counts. We never read, store, or log the actual prompt or response content.
    </p>
    <div style="background: #0f172a; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem;">
        <div style="color: #64748b; font-size: 0.8rem; margin-bottom: 0.75rem;">Example response from Privatemode (simplified):</div>
        <pre style="color: #e2e8f0; font-size: 0.8rem; margin: 0; overflow-x: auto;"><code>{{
  "choices": [...],  <span style="color: #64748b;">// We ignore this - your actual content</span>
  "usage": {{
    "prompt_tokens": 25,      <span style="color: #22c55e;">// We read this for billing</span>
    "completion_tokens": 150, <span style="color: #22c55e;">// We read this for billing</span>
    "total_tokens": 175       <span style="color: #22c55e;">// We read this for billing</span>
  }}
}}</code></pre>
    </div>
    <p style="color: #94a3b8; font-size: 0.875rem; line-height: 1.6;">
        This means we can tell you how many tokens you used and calculate costs,
        but we have no idea what you actually asked the AI or what it responded with.
        Your conversations remain completely private.
    </p>
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">Available API Endpoints</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.6;">
        This proxy supports the same endpoints as the OpenAI API. All endpoints require authentication
        via the <code style="background: #0f172a; padding: 0.125rem 0.5rem; border-radius: 4px;">Authorization: Bearer YOUR_KEY</code> header.
    </p>
    <div style="background: #0f172a; border-radius: 8px; padding: 1.25rem;">
        <div style="display: grid; gap: 1rem; font-size: 0.9375rem;">
            <div>
                <code style="color: #22c55e; margin-right: 0.75rem;">POST</code>
                <code style="color: #e2e8f0;">/v1/chat/completions</code>
                <span style="color: #64748b; margin-left: 1rem;">- Chat with AI models</span>
            </div>
            <div>
                <code style="color: #22c55e; margin-right: 0.75rem;">POST</code>
                <code style="color: #e2e8f0;">/v1/embeddings</code>
                <span style="color: #64748b; margin-left: 1rem;">- Generate text embeddings for search/RAG</span>
            </div>
            <div>
                <code style="color: #22c55e; margin-right: 0.75rem;">POST</code>
                <code style="color: #e2e8f0;">/v1/audio/transcriptions</code>
                <span style="color: #64748b; margin-left: 1rem;">- Convert audio to text</span>
            </div>
            <div>
                <code style="color: #3b82f6; margin-right: 0.75rem;">GET</code>
                <code style="color: #e2e8f0;">/health</code>
                <span style="color: #64748b; margin-left: 1rem;">- Check if the proxy is running (no auth needed)</span>
            </div>
        </div>
    </div>
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">Pricing</h3>
    <p style="color: #94a3b8; font-size: 0.875rem; margin-bottom: 1rem; line-height: 1.6;">
        All prices are in Euros. Token usage is tracked on the Usage &amp; Costs page.
    </p>
    <div style="background: #0f172a; border-radius: 8px; padding: 1.25rem;">
        <div style="display: grid; gap: 1rem; font-size: 0.9375rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #e2e8f0;">Chat Models</span>
                    <span style="color: #64748b; margin-left: 0.5rem;">(gpt-oss-120b, gemma-3-27b, qwen3-coder)</span>
                </div>
                <span style="color: #22c55e; font-family: monospace;">€5.00 per 1 million tokens</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #e2e8f0;">Text Embeddings</span>
                    <span style="color: #64748b; margin-left: 0.5rem;">(qwen3-embedding-4b)</span>
                </div>
                <span style="color: #22c55e; font-family: monospace;">€0.13 per 1 million tokens</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #e2e8f0;">Speech to Text</span>
                    <span style="color: #64748b; margin-left: 0.5rem;">(whisper-large-v3)</span>
                </div>
                <span style="color: #22c55e; font-family: monospace;">€0.096 per megabyte</span>
            </div>
        </div>
    </div>
</div>

<div class="card">
    <h3 style="margin-bottom: 1rem;">Useful Links</h3>
    <div style="display: grid; gap: 0.75rem; font-size: 0.9375rem;">
        <a href="https://privatemode.ai/docs" target="_blank" style="color: #60a5fa;">
            Privatemode Documentation - Learn more about the encryption technology
        </a>
        <a href="https://github.com/Open-Paws" target="_blank" style="color: #60a5fa;">
            Open Paws GitHub - Source code and contributions
        </a>
        <a href="https://openpaws.ai" target="_blank" style="color: #60a5fa;">
            Open Paws Website - About the project
        </a>
    </div>
</div>
"""


async def admin_about(request: web.Request) -> web.Response:
    """Show about page."""
    if not ADMIN_PASSWORD:
        return web.Response(
            text="Admin UI disabled. Set ADMIN_PASSWORD environment variable to enable.",
            status=403
        )

    if not check_admin_auth(request):
        raise web.HTTPFound('/admin/login')

    content = ABOUT_CONTENT.format(csrf_token=generate_csrf_token(session_token(request)))
    html = HTML_TEMPLATE.format(content=content)
    return web.Response(text=html, content_type='text/html')


async def admin_static(request: web.Request) -> web.Response:
    """Serve static files (logo, etc.)."""
    filename = request.match_info.get('filename', '')

    # Security: allowlist maps filenames to (relative path, content type).
    # The user-controlled value is only used as a dict key — the filesystem
    # path is constructed entirely from hardcoded values, breaking taint flow.
    static_dir = Path(__file__).parent / 'static'
    allowed_files = {
        'logo.png': (static_dir / 'logo.png', 'image/png'),
        'admin.js': (static_dir / 'admin.js', 'text/javascript'),
    }

    entry = allowed_files.get(filename)
    if entry is None:
        raise web.HTTPNotFound()

    file_path, content_type = entry
    if not file_path.exists():
        raise web.HTTPNotFound()

    with open(file_path, 'rb') as f:
        return web.Response(body=f.read(), content_type=content_type)


# Every admin route, and the handler that serves it. The auth middleware lets
# exactly these handlers through without an API key (they check the admin
# session themselves), so a route is either listed here or needs an API key.
ADMIN_ROUTES = (
    ('GET', '/admin', admin_dashboard),
    ('GET', '/admin/settings', admin_settings),
    ('POST', '/admin/settings/rate-limits', admin_save_rate_limits),
    ('GET', '/admin/usage', admin_usage),
    ('GET', '/admin/about', admin_about),
    ('GET', '/admin/static/{filename}', admin_static),
    ('GET', '/admin/login', admin_login_page),
    ('POST', '/admin/login', admin_login_post),
    ('POST', '/admin/logout', admin_logout),
    ('POST', '/admin/keys/generate', admin_generate_key),
    ('POST', '/admin/keys/{key_id}/revoke', admin_revoke_key),
    ('POST', '/admin/keys/{key_id}/enable', admin_enable_key),
    ('POST', '/admin/keys/{key_id}/delete', admin_delete_key),
    ('POST', '/admin/keys/{key_id}/rate-limit', admin_update_key_rate_limit),
)

ADMIN_HANDLERS = frozenset(handler for _, _, handler in ADMIN_ROUTES)


def setup_admin_routes(app: web.Application) -> None:
    """Add admin routes to the app."""
    for method, path, handler in ADMIN_ROUTES:
        app.router.add_route(method, path, handler)
