"""Module containing configuration classes for fabricatio-memory."""

from dataclasses import dataclass
from pathlib import Path

from fabricatio_core import CONFIG


@dataclass(frozen=True)
class MemoryConfig:
    """Configuration for fabricatio-memory."""

    memory_record_template: str = "built-in/memory_record"
    """Template for recording memory."""
    memory_recall_template: str = "built-in/memory_recall"
    """Template for recalling memory."""
    sremember_template: str = "built-in/sremember"
    """Template for selective remembering."""
    
    memory_store_root:Path = Path.home().joinpath(".fabricatio-memory")
    """Root directory for memory store."""
    writer_buffer_size: int = 50000000
    """Buffer size for memory store writer. In bytes."""
    cache_size: int = 10
    """Cache size for memory store."""
memory_config = CONFIG.load("memory", MemoryConfig)
__all__ = ["memory_config"]
