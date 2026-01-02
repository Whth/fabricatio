"""Provide a memory system to remember things."""

from abc import ABC
from typing import Optional, Self, Unpack

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.capabilities.propose import Propose
from fabricatio_core.models.generic import ScopedConfig
from fabricatio_core.models.kwargs_types import GenerateKwargs, LLMKwargs, ValidateKwargs
from fabricatio_core.utils import fallback_kwargs, ok
from pydantic import Field, PrivateAttr

from fabricatio_memory.config import memory_config
from fabricatio_memory.inited_memory_service import MEMORY_SERVICE
from fabricatio_memory.models.note import Note
from fabricatio_memory.rust import MemoryStore


class RememberScopedConfig(ScopedConfig):
    """Configuration class for memory-related settings in the Remember capability."""

    memory_llm: GenerateKwargs = Field(default_factory=GenerateKwargs)
    """Configuration for LLM generation parameters used in memory operations."""
    memory_store_name: Optional[str] = Field(default=None)
    """The memory system instance used for storing and retrieving memories."""

    _memory_store: Optional[MemoryStore] = PrivateAttr(default=None)


class Remember(Propose, RememberScopedConfig, ABC):
    """Provide a memory system to remember things."""

    def mount_memory_store(self, memory_store: Optional[MemoryStore] = None) -> Self:
        """Mount a memory system to the capability."""
        self._memory_store = memory_store or MEMORY_SERVICE.get_store(ok(self.memory_store_name))
        return self

    def unmount_memory_system(self) -> Self:
        """Unmount the memory system from the capability."""
        self._memory_store = None
        return self

    def access_memory_system(self, fallback_default: Optional[MemoryStore] = None) -> MemoryStore:
        """Access the memory system."""
        if self._memory_store is None:
            self.mount_memory_store(fallback_default)
        return ok(self._memory_store)

    async def record(self, raw: str, **kwargs: Unpack[ValidateKwargs[Note]]) -> Note:
        """Record a piece of information into the memory system.

        Args:
            raw: The raw string content to be recorded.
            **kwargs: Additional keyword arguments for generation.

        Returns:
            A Memory object representing the recorded information.
        """
        note = ok(
            await self.propose(
                Note,
                TEMPLATE_MANAGER.render_template(memory_config.memory_record_template, {"raw": raw}),
                **fallback_kwargs(kwargs, **self.memory_llm),
            ),
            "Fatal error: Note not found.",
        )

        mem_id = self.access_memory_system().add_memory(
            note.content,
            note.importance,
            note.tags,
        )
        logger.debug(f"Memory recorded: {mem_id}")
        return note

    async def recall(self, query: str, top_k: int = 100, boost_recent: bool = True, **kwargs: Unpack[LLMKwargs]) -> str:
        """Recall information from the memory system based on a query, Process with llm, which make a summary over memories.

        Args:
            query: The query string to search for relevant memories.
            top_k: The number of top memories to retrieve.
            boost_recent: Whether to boost the relevance of more recent memories.
            **kwargs: Additional keyword arguments for generation.

        Returns:
            A string containing the recalled information.
        """
        mem_seq = self.access_memory_system().search_memories(query, top_k, boost_recent)
        logger.debug(f"{len(mem_seq)} memories recalled, ids: {[mem.uuid for mem in mem_seq]}")
        return await self.aask(
            TEMPLATE_MANAGER.render_template(
                memory_config.memory_recall_template, {"query": query, "mem_seq": [mem.to_dict() for mem in mem_seq]}
            ),
            **fallback_kwargs(kwargs, **self.memory_llm),
        )
