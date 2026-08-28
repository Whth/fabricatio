"""Configuration for fabricatio-comfyui."""

from dataclasses import dataclass

from fabricatio_core import CONFIG

__all__ = ["ComfyUIConfig", "comfyui_config"]


@dataclass(frozen=True)
class ComfyUIConfig:
    """Configuration for the ComfyUI API client."""

    base_url: str = "http://127.0.0.1:8188"
    """Base URL of the ComfyUI server (default localhost:8188)."""

    timeout: float = 300.0
    """Default timeout in seconds for API requests (default 5 min)."""

    checkpoint: str | None = None
    """Default checkpoint filename on the server.

    Overrides the bundled workflow template's hardcoded checkpoint for
    every generation; a per-call ``checkpoint=`` knob takes precedence.
    """


comfyui_config = CONFIG.load("comfyui", ComfyUIConfig)
"""Singleton ComfyUI config loaded from fabricatio config chain."""
