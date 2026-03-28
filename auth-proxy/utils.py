"""
Shared utility functions for the auth proxy.
"""

from aiohttp import web
from config import TRUST_PROXY


def get_client_ip(request: web.Request) -> str:
    """
    Get client IP address from request.

    Only trusts X-Forwarded-For header if TRUST_PROXY is enabled.
    This prevents IP spoofing when not behind a trusted reverse proxy.
    """
    if TRUST_PROXY:
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip()
    return request.remote or 'unknown'
