"""
Shared Async HTTP client for ETL service.
Reuses a single httpx.AsyncTenant with keep-alive to reduce latency.
"""
from typing import Optional
import httpx

_client: Optional[httpx.AsyncTenant] = None


def get_async_client() -> httpx.AsyncTenant:
    global _client
    if _client is None:
        _client = httpx.AsyncTenant(
            timeout=5.0,
            verify=False,  # local dev
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
    return _client

