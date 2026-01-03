"""Initialize and provide access to the memory service instance.

This module creates a singleton instance of the MemoryService from the Rust backend,
configured with parameters from the global memory configuration.
"""

from fabricatio_core.decorators import once

from fabricatio_memory.config import memory_config
from fabricatio_memory.rust import MemoryService


@once
def get_memory_service() -> MemoryService:
    """Get the singleton instance of the MemoryService."""
    return MemoryService(memory_config.memory_store_root, memory_config.writer_buffer_size, memory_config.cache_size)
