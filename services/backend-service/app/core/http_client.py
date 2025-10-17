"""
Shared Async HTTP client for Backend service.
Reuses a single httpx.AsyncClient with keep-alive to reduce latency.
"""
from typing import Optional
import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

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


async def cleanup_async_client():
    """
    Cleanup the global async HTTP client to prevent event loop errors during shutdown.
    """
    global _client
    if _client is not None:
        try:
            await _client.aclose()
            logger.debug("Global HTTP client cleaned up successfully")
        except Exception as e:
            # Suppress cleanup errors to avoid noise in logs during shutdown
            logger.debug(f"Error during HTTP client cleanup (suppressed): {e}")
        finally:
            _client = None


def cleanup_async_client_sync():
    """
    Synchronous wrapper for cleanup_async_client for use in non-async contexts.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule cleanup as a task
            asyncio.create_task(cleanup_async_client())
        else:
            # If loop is not running, run cleanup directly
            loop.run_until_complete(cleanup_async_client())
    except RuntimeError:
        # Event loop is closed or not available, skip cleanup
        global _client
        _client = None

