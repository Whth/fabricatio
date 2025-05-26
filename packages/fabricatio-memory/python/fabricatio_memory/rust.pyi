from typing import List, Optional, Dict, Tuple

class Memory:
    """
    A memory item with metadata including importance, timestamps, and access patterns.
    """
    
    id: int
    content: str
    timestamp: int
    importance: float
    tags: List[str]
    access_count: int
    last_accessed: int
    
    def __init__(self, id: int, content: str, importance: float, tags: List[str]) -> None:
        """
        Create a new memory with the given ID, content, importance score, and tags.
        
        Args:
            id: Unique identifier for this memory
            content: The memory content
            importance: Importance score (0.0 to 1.0)
            tags: List of tags associated with this memory
        """
        ...
    
    def update_access(self) -> None:
        """
        Update the access count and last accessed timestamp for this memory.
        """
        ...
    
    def calculate_relevance_score(self, decay_factor: float) -> float:
        """
        Calculate a relevance score based on importance, recency, and access frequency.
        
        Args:
            decay_factor: Factor controlling how much recency affects the score
            
        Returns:
            The calculated relevance score
        """
        ...

class MemorySystem:
    """
    A full-text search memory system using Tantivy for indexing and retrieval.
    
    This system provides comprehensive memory management with features like:
    - Full-text search with Chinese language support (Jieba tokenization)
    - Importance-based ranking
    - Tag-based categorization
    - Access pattern tracking
    - Memory consolidation and cleanup
    """
    
    def __init__(self) -> None:
        """
        Initialize a new MemorySystem with an empty in-memory search index.
        """
        ...
    
    def add_memory(self, content: str, importance: float, tags: List[str]) -> int:
        """
        Add a new memory to the system.
        
        Args:
            content: The content to store
            importance: Importance score (0.0 to 1.0)
            tags: List of tags to associate with this memory
            
        Returns:
            The unique ID assigned to this memory
        """
        ...
    
    def get_memory(self, id: int) -> Optional[Memory]:
        """
        Retrieve a memory by its ID and update its access statistics.
        
        Args:
            id: The unique identifier of the memory
            
        Returns:
            The Memory object if found, None otherwise
        """
        ...
    
    def update_memory(self, id: int, content: Optional[str] = None, 
                     importance: Optional[float] = None, 
                     tags: Optional[List[str]] = None) -> bool:
        """
        Update an existing memory's content, importance, or tags.
        
        Args:
            id: The unique identifier of the memory to update
            content: New content (if provided)
            importance: New importance score (if provided)
            tags: New tags list (if provided)
            
        Returns:
            True if the memory was updated, False if not found
        """
        ...
    
    def delete_memory_by_id(self, id: int) -> bool:
        """
        Delete a memory by its ID.
        
        Args:
            id: The unique identifier of the memory to delete
            
        Returns:
            True if the memory was deleted
        """
        ...
    
    def search_memories(self, query_str: str, top_k: int, boost_recent: bool = False) -> List[Memory]:
        """
        Search for memories using full-text search.
        
        Args:
            query_str: The search query string
            top_k: Maximum number of results to return
            boost_recent: Whether to boost recently accessed memories in ranking
            
        Returns:
            List of matching Memory objects, ranked by relevance
        """
        ...
    
    def search_by_tags(self, tags: List[str], top_k: int) -> List[Memory]:
        """
        Search for memories by tags.
        
        Args:
            tags: List of tags to search for
            top_k: Maximum number of results to return
            
        Returns:
            List of matching Memory objects
        """
        ...
    
    def get_memories_by_importance(self, min_importance: float, top_k: int) -> List[Memory]:
        """
        Get memories with importance above a threshold.
        
        Args:
            min_importance: Minimum importance score threshold
            top_k: Maximum number of results to return
            
        Returns:
            List of Memory objects sorted by importance (descending)
        """
        ...
    
    def get_recent_memories(self, days: int, top_k: int) -> List[Memory]:
        """
        Get memories created within the specified number of days.
        
        Args:
            days: Number of days to look back
            top_k: Maximum number of results to return
            
        Returns:
            List of Memory objects sorted by timestamp (most recent first)
        """
        ...
    
    def get_frequently_accessed(self, top_k: int) -> List[Memory]:
        """
        Get the most frequently accessed memories.
        
        Args:
            top_k: Maximum number of results to return
            
        Returns:
            List of Memory objects sorted by access count (descending)
        """
        ...
    
    def consolidate_memories(self, similarity_threshold: float) -> List[Tuple[int, int]]:
        """
        Find pairs of similar memories that could be consolidated.
        
        Args:
            similarity_threshold: Minimum similarity score to consider memories similar
            
        Returns:
            List of tuples containing pairs of memory IDs that are similar
        """
        ...
    
    def cleanup_old_memories(self, days_threshold: int, min_importance: float) -> List[int]:
        """
        Remove old, low-importance, rarely accessed memories.
        
        Args:
            days_threshold: Age threshold in days
            min_importance: Minimum importance threshold
            
        Returns:
            List of IDs of memories that were removed
        """
        ...
    
    def get_all_memories(self) -> List[Memory]:
        """
        Retrieve all memories in the system.
        
        Returns:
            List of all Memory objects
        """
        ...
    
    def count_memories(self) -> int:
        """
        Get the total number of memories in the system.
        
        Returns:
            Total count of memories
        """
        ...
    
    def get_memory_stats(self) -> Dict[str, float]:
        """
        Get statistical information about the memory system.
        
        Returns:
            Dictionary containing statistics like total_memories, avg_importance, 
            avg_access_count, and avg_age_days
        """
        ...