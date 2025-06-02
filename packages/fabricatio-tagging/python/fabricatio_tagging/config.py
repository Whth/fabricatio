"""Module containing configuration classes for fabricatio-tagging."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class TaggingConfig:
    """Configuration for fabricatio-tagging."""

    tagging_template: str = "tagging"
    """The template to use for tagging."""


tagging_config = CONFIG.load("tagging", TaggingConfig)
__all__ = ["tagging_config"]
