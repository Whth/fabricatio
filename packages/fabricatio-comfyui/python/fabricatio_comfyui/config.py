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
    """Default timeout in seconds for API requests (default 5 min)."""

    pool_size: int = 10
    """Maximum number of concurrent connections in the httpx connection pool."""


comfyui_config = CONFIG.load("comfyui", ComfyuiConfig)
"""Singleton ComfyUI config loaded from fabricatio config chain."""
