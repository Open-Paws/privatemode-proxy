"""
Shared configuration for the auth proxy.

Centralizes environment variable loading and default values to avoid
duplication across modules.
"""

import os

# File paths
API_KEYS_FILE = os.environ.get('API_KEYS_FILE', '/app/secrets/api_keys.json')
SETTINGS_FILE = os.environ.get('SETTINGS_FILE', '/app/secrets/settings.json')
USAGE_FILE = os.environ.get('USAGE_FILE', '/app/data/usage.json')

# Server configuration
# Default assumes both services run in same container (supervisord setup)
# Override with UPSTREAM_URL env var for different deployments
UPSTREAM_URL = os.environ.get('UPSTREAM_URL', 'http://127.0.0.1:8081')
PORT = int(os.environ.get('PORT', '8080'))
PRIVATEMODE_API_KEY = os.environ.get('PRIVATEMODE_API_KEY', '')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')

# Trust proxy headers (X-Forwarded-For, X-Forwarded-Proto, etc.)
# Set to 'true' when running behind a trusted reverse proxy (nginx, Fly.io, etc.)
# When false, X-Forwarded-For headers are ignored to prevent IP spoofing
TRUST_PROXY = os.environ.get('TRUST_PROXY', 'false').lower() in ('true', '1', 'yes')

# Number of trusted reverse proxies in front of the app. With TRUST_PROXY on,
# the client IP is the entry this many places from the RIGHT of X-Forwarded-For
# (the leftmost entries are whatever the client chose to send).
TRUSTED_PROXY_HOPS = max(1, int(os.environ.get('TRUSTED_PROXY_HOPS', '1')))

# Default rate limits
# RATE_LIMIT_REQUESTS is the ceiling across ALL keys combined;
# KEY_RATE_LIMIT_REQUESTS applies to each key that has no limit of its own,
# so one key cannot use up the whole shared ceiling.
DEFAULT_RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', '100'))
DEFAULT_RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', '60'))
DEFAULT_KEY_RATE_LIMIT_REQUESTS = int(os.environ.get('KEY_RATE_LIMIT_REQUESTS', '60'))
DEFAULT_IP_RATE_LIMIT_REQUESTS = int(os.environ.get('IP_RATE_LIMIT_REQUESTS', '1000'))
DEFAULT_IP_RATE_LIMIT_WINDOW = int(os.environ.get('IP_RATE_LIMIT_WINDOW', '60'))

# Usage metadata retention. Usage is stored as daily totals per key/model/endpoint
# (never per request, never content) and deleted after this many days.
USAGE_RETENTION_DAYS = max(1, int(os.environ.get('USAGE_RETENTION_DAYS', '400')))

# TLS configuration
# Set TLS_CERT_FILE and TLS_KEY_FILE to enable HTTPS
# If not set, server runs in HTTP mode
TLS_CERT_FILE = os.environ.get('TLS_CERT_FILE', '')
TLS_KEY_FILE = os.environ.get('TLS_KEY_FILE', '')
TLS_ENABLED = bool(TLS_CERT_FILE and TLS_KEY_FILE)

# Force HTTPS - reject non-HTTPS requests (default: true when TLS is enabled)
# When behind a trusted proxy, checks X-Forwarded-Proto header
# Set to 'false' to allow HTTP (not recommended for production)
_force_https_default = 'true' if TLS_ENABLED else 'false'
FORCE_HTTPS = os.environ.get('FORCE_HTTPS', _force_https_default).lower() in ('true', '1', 'yes')
