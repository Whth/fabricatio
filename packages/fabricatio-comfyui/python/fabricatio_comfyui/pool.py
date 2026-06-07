"""URL-based client pool for ComfyUI.

Provides :func:`get_client` to obtain a shared :class:`ComfyuiClient` keyed by
targeting the same ComfyUI server reuse the same underlying HTTP pool.
"""

from typing import Dict

from fabricatio_comfyui.client import ComfyuiClient
from fabricatio_comfyui.config import comfyui_config

__all__ = ["close_all", "get_client"]

_CLIENT_POOL: Dict[str, ComfyuiClient] = {}
"""Map of normalised base_url → shared client instance."""


def _normalise(url: str) -> str:
    return url.rstrip("/").lower()


def get_client(base_url: str | None = None) -> ComfyuiClient:
    """Return (or lazily create) a shared client for *base_url*.

    Args:
        base_url: ComfyUI server URL.  ``None`` uses ``comfyui_config.base_url``.

    Returns:
        An open :class:`ComfyuiClient` ready for use.
    """
    url = _normalise(base_url or comfyui_config.base_url)
    client = _CLIENT_POOL.get(url)
    if client is None:
        client = ComfyuiClient()
        client.open()
        _CLIENT_POOL[url] = client
    return client


async def close_all() -> None:
    """Close every pooled client.  Call at application shutdown."""
    for client in _CLIENT_POOL.values():
        await client.close()
    _CLIENT_POOL.clear()
