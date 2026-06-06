"""Configuration for fabricatio-comfyui."""

from dataclasses import dataclass

from fabricatio_core import CONFIG

__all__ = ["ComfyuiConfig", "comfyui_config"]


@dataclass(frozen=True)
class ComfyuiConfig:
    """Configuration for the ComfyUI API client."""
    base_url: str = "http://127.0.0.1:8188"
    """Base URL of the ComfyUI server (default localhost:8188)."""
    timeout: float = 300.0
    """Default timeout in seconds for HTTP API requests (default 5 min)."""
    pool_size: int = 10
    """Maximum number of concurrent connections in the httpx connection pool."""
    ws_timeout: float = 600.0
    """Timeout for WebSocket-based generation (default 10 min).
    WebSocket connections may need a longer timeout than HTTP for large images
    or complex workflows with many upscaling steps.
    """
    use_websocket: bool = True
    """Whether to use WebSocket for completion detection in ``generate()``.
    When ``True`` (default), ``generate()`` uses WebSocket (Method 2) for
    real-time execution monitoring.  When ``False``, falls back to HTTP
    polling via ``wait_for_completion()``.
    """


comfyui_config = CONFIG.load("comfyui", ComfyuiConfig)
"""Singleton ComfyUI config loaded from fabricatio config chain."""
