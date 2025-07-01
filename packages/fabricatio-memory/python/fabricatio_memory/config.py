"""Module containing configuration classes for fabricatio-memory."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class MemoryConfig:
    """Configuration for fabricatio-memory."""

    memory_record_template: str = "memory_record"
    """Template for recording memory."""
    memory_recall_template: str = "memory_recall"
    """Template for recalling memory."""
    sremember_template: str = "sremember"
    """Template for selective remembering."""


memory_config = CONFIG.load("memory", MemoryConfig)
__all__ = ["memory_config"]
