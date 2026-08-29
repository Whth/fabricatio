"""Module containing configuration classes for fabricatio-context."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class ContextConfig:
    """Configuration for fabricatio-context."""


context_config = CONFIG.load("context", ContextConfig)

__all__ = ["context_config"]
