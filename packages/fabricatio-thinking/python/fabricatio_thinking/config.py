"""Module containing configuration classes for fabricatio-thinking."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class ThinkingConfig:
    """Configuration for fabricatio-thinking."""


thinking_config = CONFIG.load("thinking", ThinkingConfig)

__all__ = ["thinking_config"]
