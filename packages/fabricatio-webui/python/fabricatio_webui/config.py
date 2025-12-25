"""Module containing configuration classes for fabricatio-webui."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class WebuiConfig:
    """Configuration for fabricatio-webui."""


webui_config = CONFIG.load("webui", WebuiConfig)

__all__ = ["webui_config"]
