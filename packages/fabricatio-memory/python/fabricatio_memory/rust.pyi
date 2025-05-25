"""Rust bindings for the Rust API of fabricatio-memory."""

from typing import List

class MemorySystem:
    """
    A memory system that stores and manages memories with importance-based decay.
    
    This class implements a memory storage system with LSTM-like gates for managing
    what to remember, what to recall, and what to forget. Memories are stored with
    metadata including timestamps, importance scores, and access patterns.
    """
    
    def __init__(self) -> None:
        """
        Initialize a new MemorySystem with an empty memory storage.
        
        The storage schema includes:
        - id: Unique identifier for each memory
        - timestamp: When the memory was created
        - content: The actual memory content
        - importance: Initial importance score (0.0 to 1.0)
        - last_accessed: Last time this memory was accessed
        - access_count: Number of times this memory has been accessed
        - decay_rate: Rate at which importance decays over time
        """
        ...
    
    def remember(self, id: int, content: str, importance: float) -> None:
        """
        Add a new memory to the storage system.
        
        Args:
            id: Unique identifier for this memory
            content: The content to remember
            importance: Initial importance score (0.0 to 1.0)
        """
        ...
    
    def input_gate(self, new_content: str, current_context: str) -> bool:
        """
        Determine whether new content should be remembered based on semantic similarity.
        
        The input gate filters incoming information to prevent storing redundant or
        irrelevant memories. It uses semantic similarity to compare new content with
        the current context.
        
        Args:
            new_content: The new content to potentially remember
            current_context: The current context for comparison
            
        Returns:
            True if the content should be remembered (similarity > 0.7), False otherwise
        """
        ...
    
    def output_gate(self, context: str, top_k: int) -> List[str]:
        """
        Recall the most relevant memories based on the current context.
        
        The output gate retrieves memories that are most relevant to the given context,
        ranked by a combination of semantic similarity and importance scores.
        
        Args:
            context: The current context to match against stored memories
            top_k: Maximum number of memories to return
            
        Returns:
            List of the top-k most relevant memory contents
        """
        ...
    
    def forget_gate(self) -> None:
        """
        Remove low-value memories based on importance decay over time.
        
        The forget gate implements a time-based decay mechanism where memories lose
        importance over time. Memories with decayed importance below 0.2 are removed.
        The decay formula is: importance * 0.95^(hours_since_creation)
        """
        ...
    
    def get_all_memories(self) -> List[str]:
        """
        Retrieve all stored memory contents.
        
        This method is primarily intended for debugging and inspection purposes.
        
        Returns:
            List of all memory contents currently in storage
        """
        ...