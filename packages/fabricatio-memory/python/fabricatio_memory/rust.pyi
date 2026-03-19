import builtins
import os
import pathlib
import typing

MAX_IMPORTANCE_SCORE: builtins.int = 100
MIN_IMPORTANCE_SCORE: builtins.int = 0

@typing.final
class Memory:
    """Represents a memory object with content, importance, tags, and access statistics."""

    @property
    def uuid(self) -> builtins.str:
        """Unique identifier for the memory."""

    @property
    def content(self) -> builtins.str:
        """Content of the memory."""

    @property
    def timestamp(self) -> builtins.int:
        """Unix timestamp when the memory was created."""

    @property
    def importance(self) -> builtins.int:
        """Importance score of the memory (0 to MAX_IMPORTANCE_SCORE)."""

    @property
    def tags(self) -> builtins.list[builtins.str]:
        """List of tags associated with the memory."""

    @property
    def access_count(self) -> builtins.int:
        """Number of times the memory has been accessed."""

    @property
    def last_accessed(self) -> builtins.int:
        """Unix timestamp when the memory was last accessed."""

    def to_dict(self) -> dict:
        """Convert the memory to a Python dictionary.

        Returns:
            dict: A dictionary representation of the memory object.
        """

@typing.final
class MemoryService:
    """Service class for managing memory stores and indexes."""

    def __new__(
        cls,
        store_root_directory: builtins.str | os.PathLike | pathlib.Path,
        writer_buffer_size: builtins.int = 15000000,
        cache_size: builtins.int = 10,
    ) -> MemoryService:
        """Creates a new MemoryService instance.

        Args:
            store_root_directory: The root directory where indexes will be stored.
            writer_buffer_size: The buffer size for index writers (default: 15MB).
            cache_size: The maximum number of indexes to keep in cache (default: 10).

        Returns:
            MemoryService: A new instance of MemoryService.
        """

    def get_store(self, store_name: builtins.str) -> MemoryStore:
        """Get a MemoryStore instance for the given store name.

        This method retrieves or creates an index for the given store name,
        then returns a MemoryStore instance that can be used to perform
        operations on that index.

        Args:
            store_name: The name of the store to get.

        Returns:
            MemoryStore: A MemoryStore instance for the given store name.

        Raises:
            ValueError: If the store name is invalid.
            RuntimeError: If there's an error creating or opening the index.
            RuntimeError: If there's an error creating the MemoryStore instance.
        """

    def list_stores(self, cached_only: builtins.bool = False) -> builtins.list[builtins.str]:
        """List all stores in the system.

        This method returns a list of all store names. It can optionally return
        only the stores that are currently cached in memory.

        Args:
            cached_only: If true, only return stores that are currently cached in memory.
                         If false (default), return all stores in the store directory.

        Returns:
            list[str]: A list of store names.

        Raises:
            RuntimeError: If there's an error reading the store directory.
        """

@typing.final
class MemoryStats:
    """Memory statistics structure containing aggregated metrics about stored memories."""

    @property
    def total_memories(self) -> builtins.int:
        """Total number of memories stored."""

    @property
    def avg_importance(self) -> builtins.float:
        """Average importance score across all memories."""

    @property
    def avg_access_count(self) -> builtins.float:
        """Average number of times memories have been accessed."""

    @property
    def avg_age_days(self) -> builtins.float:
        """Average age of memories in days."""

    def display(self) -> builtins.str:
        """Display memory statistics in a formatted string.

        Returns:
            str: A formatted string containing the memory statistics.
        """

@typing.final
class MemoryStore:
    """MemoryStore is a struct that provides an interface for storing, retrieving, and searching memories in a Tantivy search index.

    It supports operations such as adding, updating, deleting, and searching
    memories based on various criteria like content, tags, importance, recency, and access frequency.

    The store handles memory access tracking by updating access counts and timestamps automatically
    during retrieval and search operations. It also supports batch updates and optional immediate
    disk writes for consistency.

    The implementation uses a Tantivy index with fields for content, tags, importance, timestamps,
    and access counts. It includes PyO3 bindings to allow Python usage.
    """

    def add_memory(
        self,
        content: builtins.str,
        importance: builtins.int,
        tags: typing.Sequence[builtins.str],
        write: builtins.bool = False,
    ) -> builtins.str:
        """Add a new memory to the system and return its ID.

        Args:
            content: The text content of the memory.
            importance: The importance score of the memory.
            tags: A sequence of tags associated with the memory.
            write: Whether to immediately write changes to disk (default: False).

        Returns:
            str: The unique UUID of the added memory.
        """

    def write(self) -> None:
        """Write all changes to disk."""

    def get_memory(self, uuid: builtins.str, write: builtins.bool = False) -> typing.Optional[Memory]:
        """Retrieve a memory by its ID and update its access count.

        Args:
            uuid: The unique identifier of the memory to retrieve.
            write: Whether to immediately write changes to disk after updating stats (default: False).

        Returns:
            Memory | None: The retrieved memory object, or None if not found.
        """

    def update_memory(
        self,
        uuid: builtins.str,
        content: typing.Optional[builtins.str] = None,
        importance: typing.Optional[builtins.int] = None,
        tags: typing.Optional[typing.Sequence[builtins.str]] = None,
        write: builtins.bool = False,
    ) -> builtins.bool:
        """Update an existing memory's content, importance, or tags.

        Args:
            uuid: The unique identifier of the memory to update.
            content: New content for the memory (optional).
            importance: New importance score for the memory (optional).
            tags: New tags for the memory (optional).
            write: Whether to immediately write changes to disk (default: False).

        Returns:
            bool: True if the memory was updated successfully, False otherwise.
        """

    def delete_memory(self, uuid: builtins.str, write: builtins.bool = False) -> builtins.bool:
        """Delete a memory by its ID.

        Args:
            uuid: The unique identifier of the memory to delete.
            write: Whether to immediately write changes to disk (default: False).

        Returns:
            bool: True if the memory was deleted successfully, False otherwise.
        """

    def search_memories(
        self,
        query_str: builtins.str,
        top_k: builtins.int = 20,
        boost_recent: builtins.bool = False,
        write: builtins.bool = False,
    ) -> builtins.list[Memory]:
        """Search memories by query string with optional recency boosting.

        Args:
            query_str: The search query string.
            top_k: Maximum number of results to return (default: 20).
            boost_recent: Whether to boost recent memories in ranking (default: False).
            write: Whether to immediately write changes to disk (default: False).

        Returns:
            list[Memory]: A list of matching Memory objects sorted by relevance.
        """

    def search_by_tags(
        self, tags: typing.Sequence[builtins.str], top_k: builtins.int = 20, write: builtins.bool = False
    ) -> builtins.list[Memory]:
        """Search memories by tags.

        Args:
            tags: A sequence of tags to search for.
            top_k: Maximum number of results to return (default: 20).
            write: Whether to immediately write changes to disk (default: False).

        Returns:
            list[Memory]: A list of matching Memory objects.
        """

    def get_memories_by_importance(
        self, min_importance: builtins.int, top_k: builtins.int = 20, write: builtins.bool = False
    ) -> builtins.list[Memory]:
        """Get memories filtered by minimum importance level.

        Args:
            min_importance: The minimum importance score required.
            top_k: Maximum number of results to return (default: 20).
            write: Whether to immediately write changes to disk (default: False).

        Returns:
            list[Memory]: A list of Memory objects meeting the importance criteria.
        """

    def get_recent_memories(
        self, days: builtins.int, top_k: builtins.int = 20, write: builtins.bool = False
    ) -> builtins.list[Memory]:
        """Get memories from the last N days.

        Args:
            days: Number of days to look back.
            top_k: Maximum number of results to return (default: 20).
            write: Whether to immediately write changes to disk (default: False).

        Returns:
            list[Memory]: A list of Memory objects created within the specified timeframe.
        """

    def get_frequently_accessed(
        self, top_k: builtins.int = 20, write: builtins.bool = False
    ) -> builtins.list[Memory]:
        """Get memories sorted by access frequency.

        Args:
            top_k: Maximum number of results to return (default: 20).
            write: Whether to immediately write changes to disk (default: False).

        Returns:
            list[Memory]: A list of Memory objects sorted by access count descending.
        """

    def count_memories(self) -> builtins.int:
        """Count the total number of memories in the system.

        Returns:
            int: The total count of memories.
        """

    def stats(self) -> MemoryStats:
        """Get aggregated statistics about all memories.

        Returns:
            MemoryStats: An object containing aggregated statistics.
        """
