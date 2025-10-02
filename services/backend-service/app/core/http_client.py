"""
Shared Async HTTP client for Backend service.
Reuses a single httpx.AsyncClient with keep-alive to reduce latency.
"""
from typing import Optional
import httpx

_client: Optional[httpx.AsyncClient] = None


def get_async_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=5.0,
            verify=False,  # local dev
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
    return _client

