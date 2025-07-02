"""Rust bindings for the MemorySystem class."""

from typing import Dict, List, Optional

class Memory:
    """Represents a memory item with content, metadata, and access statistics."""

    id: int
    """Unique identifier for the memory item."""

    content: str
    """Textual content of the memory."""

    importance: float
    """Numerical value representing the importance of the memory (0.0 to 1.0)."""

    tags: List[str]
    """List of string tags associated with the memory for categorization and searching."""
    timestamp: int
    """Timestamp indicating when the memory was created (in seconds since epoch)."""
    access_count: int
    """Number of times this memory has been accessed."""
    last_accessed: int
    """Timestamp indicating the last time the memory was accessed (in seconds since epoch)."""
    def to_dict(self) -> Dict:
        """Converts the Memory object to a dictionary."""

class MemoryStats:
    """Contains statistical data about the memories in the MemorySystem."""

    total_memories: int
    avg_importance: float
    avg_access_count: float
    avg_age_days: float

    def display(self) -> str:
        """Returns a string representation of the memory statistics.

        Returns:
            A formatted string showing total memories, average importance,
            average access count, and average age in days.
        """

class MemorySystem:
    """Manages a collection of memories.

    providing functionalities for adding, retrieving, searching, and maintaining memories. It uses a full-text search
    index for efficient querying.
    """

    def __init__(self, index_path: Optional[str] = None, writer_buffer_size: Optional[int] = None) -> None:
        """Initializes the MemorySystem.

        An in-memory index is used if index_path is None. Otherwise, it opens or creates
        an index at the given path.

        Args:
            index_path: Optional path to store the search index on disk.
            writer_buffer_size: Optional buffer size in bytes for the index writer.
                                Defaults to 50MB.
        """

    def add_memory(self, content: str, importance: float, tags: List[str]) -> int:
        """Adds a new memory to the system. A unique ID is generated for the memory.

        Args:
            content: The textual content of the memory.
            importance: The importance score of the memory.
            tags: A list of tags associated with the memory.

        Returns:
            The unique ID assigned to the newly added memory.
        """

    def get_memory(self, id: int) -> Optional[Memory]:
        """Retrieves a memory by its ID. If found, its access statistics are updated.

        Args:
            id: The unique ID of the memory to retrieve.

        Returns:
            The Memory object if found, otherwise None.
        """

    def update_memory(
        self,
        id: int,
        content: Optional[str] = None,
        importance: Optional[float] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """Updates the content, importance, or tags of an existing memory.

        Args:
            id: The ID of the memory to update.
            content: Optional new content for the memory.
            importance: Optional new importance score for the memory.
            tags: Optional new list of tags for the memory.

        Returns:
            True if the memory was found and updated, False otherwise.
        """

    def delete_memory_by_id(self, id: int) -> bool:
        """Deletes a memory from the system by its ID.

        Args:
            id: The ID of the memory to delete.

        Returns:
            True if the memory was successfully deleted. (Note: Rust impl always returns true if no error,
            doesn't check if ID existed before deletion attempt for return value).
        """

    def search_memories(self, query_str: str, top_k: int = 100, boost_recent: bool = False) -> List[Memory]:
        """Searches memories based on a query string. Results can be boosted by recency.

        Args:
            query_str: The search query.
            top_k: The maximum number of results to return. Defaults to 100.
            boost_recent: If True, scores of more recent memories are boosted. Defaults to False.

        Returns:
            A list of Memory objects matching the query, sorted by relevance.
        """

    def search_by_tags(self, tags: List[str], top_k: int = 100) -> List[Memory]:
        """Searches for memories that match any of the provided tags.

        Args:
            tags: A list of tags to search for.
            top_k: The maximum number of results to return. Defaults to 100.

        Returns:
            A list of Memory objects matching the tags.
        """

    def get_memories_by_importance(self, min_importance: float, top_k: int = 100) -> List[Memory]:
        """Retrieves memories with an importance score greater than or equal to min_importance.

        Args:
            min_importance: The minimum importance score.
            top_k: The maximum number of results to return, sorted by importance. Defaults to 100.

        Returns:
            A list of Memory objects, sorted by importance in descending order.
        """

    def get_recent_memories(self, days: int, top_k: int = 100) -> List[Memory]:
        """Retrieves memories created within the specified number of days from now.

        Args:
            days: The number of days to look back.
            top_k: The maximum number of results to return, sorted by recency. Defaults to 100.

        Returns:
            A list of Memory objects, sorted by timestamp in descending order (most recent first).
        """

    def get_frequently_accessed(self, top_k: int = 100) -> List[Memory]:
        """Retrieves the most frequently accessed memories.

        Args:
            top_k: The maximum number of results to return, sorted by access count. Defaults to 100.

        Returns:
            A list of Memory objects, sorted by access_count in descending order.
        """

    def cleanup_old_memories(self, days_threshold: int, min_importance: float) -> List[int]:
        """Removes old, low-importance, and infrequently accessed memories.

        A memory is removed if it's older than days_threshold, its importance is less than
        min_importance, and its access_count is less than 5.

        Args:
            days_threshold: The age in days beyond which memories are considered old.
            min_importance: The importance score below which memories are considered
                            for cleanup if they are old and infrequently accessed.

        Returns:
            A list of IDs of the memories that were removed.
        """

    def get_all_memories(self) -> List[Memory]:
        """Retrieves all memories currently in the system.

        Note:
            This may be performance-intensive for very large memory sets.

        Returns:
            A list of all Memory objects.
        """

    def count_memories(self) -> int:
        """Counts the total number of memories in the system.

        Returns:
            The total number of memories.
        """

    def get_memory_stats(self) -> MemoryStats:
        """Calculates and returns statistics about the memories in the system.

        Returns:
            A MemoryStats object containing statistics like total count, average importance,
            average access count, and average age.
        """
