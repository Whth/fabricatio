"""Provide a memory system to remember things."""

from typing import List, Unpack

from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.generic import ScopedConfig
from fabricatio_core.models.kwargs_types import GenerateKwargs
from pydantic import Field

from fabricatio_memory.rust import Memory, MemorySystem


class RememberScopedConfig(ScopedConfig):
    """Configuration class for memory-related settings in the Remember capability.

    Attributes:
        memory_llm: Configuration for the LLM used in memory operations.
        memory_system: The memory system implementation to use.
    """

    memory_llm: GenerateKwargs = Field(default_factory=GenerateKwargs)
    memory_system: MemorySystem = Field(default_factory=MemorySystem)


class Remember(Propose, RememberScopedConfig):
    """Provide a memory system to remember things."""

    async def record(self, raw: str, **kwargs: Unpack[GenerateKwargs]) -> Memory:
        """Record a piece of information into the memory system.

        Args:
            raw: The raw string content to be recorded.
            **kwargs: Additional keyword arguments for generation.

        Returns:
            A Memory object representing the recorded information.
        """
        ...

    async def recall(self, query: str, **kwargs: Unpack[GenerateKwargs]) -> List[Memory]:
        """Recall information from the memory system based on a query.

        Args:
            query: The query string to search for relevant memories.
            **kwargs: Additional keyword arguments for generation.

        Returns:
            A list of Memory objects matching the query.
        """
        ...
