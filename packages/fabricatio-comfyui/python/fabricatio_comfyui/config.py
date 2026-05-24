"""Module containing configuration classes for fabricatio-comfyui."""
from dataclasses import dataclass
from fabricatio_core import CONFIG

@dataclass(frozen=True)
class ComfyuiConfig:
    """ Configuration for fabricatio-comfyui"""

comfyui_config = CONFIG.load("comfyui",  ComfyuiConfig)

__all__ = [
    "comfyui_config"
]