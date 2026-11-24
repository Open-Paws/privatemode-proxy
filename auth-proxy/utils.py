"""
Shared utility functions for the auth proxy.
"""

from aiohttp import web
from config import TRUST_PROXY, TRUSTED_PROXY_HOPS, TLS_ENABLED, FORCE_HTTPS


def get_client_ip(request: web.Request) -> str:
    """
    Get client IP address from request.

    Only trusts X-Forwarded-For when TRUST_PROXY is enabled, and then takes the
    entry TRUSTED_PROXY_HOPS places from the right: each trusted proxy appends
    the address it saw, so the rightmost entries are trustworthy and the
    leftmost ones are whatever the client chose to send.
    """
    if TRUST_PROXY:
        forwarded = [
            part.strip()
            for part in request.headers.get('X-Forwarded-For', '').split(',')
            if part.strip()
        ]
        if len(forwarded) >= TRUSTED_PROXY_HOPS:
            return forwarded[-TRUSTED_PROXY_HOPS]
    return request.remote or 'unknown'


def is_https_request(request: web.Request) -> bool:
    """True if the client connection is HTTPS (directly, or via a trusted proxy)."""
    if request.secure:
        return True
    return TRUST_PROXY and request.headers.get('X-Forwarded-Proto', '').lower() == 'https'


def cookies_must_be_secure(request: web.Request) -> bool:
    """Cookies get the Secure flag whenever the deployment serves HTTPS."""
    return TLS_ENABLED or FORCE_HTTPS or is_https_request(request)


def has_dot_segment(path: str) -> bool:
    """True if a decoded URL path contains a '.' or '..' segment."""
    return any(segment in ('.', '..') for segment in path.split('/'))
