"""Module containing configuration classes for fabricatio-memory."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class MemoryConfig:
    """Configuration for fabricatio-memory."""


memory_config = CONFIG.load("memory", MemoryConfig)
__all__ = ["memory_config"]
