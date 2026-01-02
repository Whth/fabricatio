"""Initialize and provide access to the memory service instance.

This module creates a singleton instance of the MemoryService from the Rust backend,
configured with parameters from the global memory configuration.
"""
from fabricatio_memory.rust import MemoryService

from fabricatio_memory.config import memory_config

MEMORY_SERVICE = MemoryService(memory_config.memory_store_root,memory_config.writer_buffer_size,memory_config.cache_size)
"""Memory service instance."""
