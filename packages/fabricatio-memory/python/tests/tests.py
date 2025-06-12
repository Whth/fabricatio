"""Tests for the memory."""

from datetime import datetime, timedelta

import pytest

# Assuming the module name is 'memory' and the classes are exposed at module level
from fabricatio_memory.rust import Memory, MemorySystem


@pytest.fixture
def memory_system(tmpdir):
    """Fixture to create a temporary MemorySystem instance with in-memory index."""
    # Use in-memory index for testing
    return MemorySystem()


def test_add_and_get_memory(memory_system) -> None:
    """Test adding a memory and retrieving it by ID."""
    content = "Test memory content"
    importance = 0.75
    tags = ["test", "pytest"]

    memory_id = memory_system.add_memory(content, importance, tags)
    assert memory_id > 0

    memory = memory_system.get_memory(memory_id)
    assert memory is not None
    assert memory.content == content
    assert memory.importance == importance
    assert set(memory.tags) == set(tags)


def test_update_memory(memory_system) -> None:
    """Test updating memory content, importance, and tags."""
    original_content = "Original content"
    updated_content = "Updated content"
    original_importance = 0.5
    updated_importance = 0.8
    original_tags = ["original"]
    updated_tags = ["updated"]

    memory_id = memory_system.add_memory(original_content, original_importance, original_tags)

    # Update all fields
    success = memory_system.update_memory(
        memory_id, content=updated_content, importance=updated_importance, tags=updated_tags
    )
    assert success

    memory = memory_system.get_memory(memory_id)
    assert memory.content == updated_content
    assert memory.importance == updated_importance
    assert set(memory.tags) == set(updated_tags)


def test_delete_memory_by_id(memory_system) -> None:
    """Test deleting a memory by its ID."""
    memory_id = memory_system.add_memory("Test content", 0.5, ["test"])
    result = memory_system.delete_memory_by_id(memory_id)
    assert result

    # Verify that the memory is no longer retrievable
    assert memory_system.get_memory(memory_id) is None


def test_search_memories(memory_system) -> None:
    """Test searching memories using a query string."""
    # Add test data
    memory_system.add_memory("apple banana orange", 0.5, ["fruit"])
    memory_system.add_memory("carrot potato tomato", 0.6, ["vegetable"])

    results = memory_system.search_memories("apple")
    assert len(results) == 1
    assert "apple" in results[0].content

    # Test boosting recent
    results_boosted = memory_system.search_memories("tomato", boost_recent=True)
    assert len(results_boosted) == 1
    assert "tomato" in results_boosted[0].content


def test_search_by_tags(memory_system) -> None:
    """Test searching memories by tags."""
    memory_system.add_memory("Document about AI", 0.7, ["AI", "technology"])
    memory_system.add_memory("Recipe for cake", 0.6, ["cooking", "baking"])

    results = memory_system.search_by_tags(["AI"])
    assert len(results) == 1
    assert "AI" in results[0].tags

    multiple_tag_results = memory_system.search_by_tags(["cooking", "baking"])
    assert len(multiple_tag_results) == 1
    assert "cake" in multiple_tag_results[0].content


def test_get_memories_by_importance(memory_system) -> None:
    """Test retrieving memories by minimum importance threshold."""
    memory_system.add_memory("High importance item", 0.9, ["important"])
    memory_system.add_memory("Low importance item", 0.3, ["not-important"])

    results = memory_system.get_memories_by_importance(0.5)
    assert len(results) == 1
    assert results[0].importance >= 0.5

def test_get_recent_memories(memory_system) -> None:
    """Test retrieving memories created within a specified number of days."""
    # Add current memory
    current_id = memory_system.add_memory("Current memory", 0.5, ["recent"])

    # Add an older memory by creating it with the memory system
    # Since we can't manipulate timestamp directly, we'll test with what we have
    old_id = memory_system.add_memory("Old memory", 0.5, ["old"])

    # For this test, we'll just verify that get_recent_memories returns memories
    # In a real scenario, the timestamp would be set automatically when memories are created
    recent_memories = memory_system.get_recent_memories(days=365)  # Use a large range to include all memories
    assert len(recent_memories) >= 1  # At least the current memory should be included
    
    # Verify that our current memory is in the results
    memory_ids = [memory.id for memory in recent_memories]
    assert current_id in memory_ids


def test_get_frequently_accessed(memory_system) -> None:
    """Test retrieving most frequently accessed memories."""
    freq_id = memory_system.add_memory("Frequent access", 0.5, ["frequent"])

    # Simulate accesses
    for _ in range(10):
        memory_system.get_memory(freq_id)

    frequent_memories = memory_system.get_frequently_accessed(top_k=1)
    assert len(frequent_memories) == 1
    assert frequent_memories[0].access_count == 10


def test_consolidate_memories(memory_system) -> None:
    """Test identifying similar memories based on content."""
    memory_system.add_memory("Apple banana cherry date", 0.7, ["fruits"])
    memory_system.add_memory("Banana cherry date elderberry", 0.6, ["more fruits"])

    similar_pairs = memory_system.consolidate_memories(similarity_threshold=0.5)
    assert len(similar_pairs) > 0
    assert tuple(sorted(similar_pairs[0])) == (1, 2)  # Ordered pair

def test_cleanup_old_memories(memory_system) -> None:
    """Test cleaning up old, low-importance, infrequently accessed memories."""
    # Add a low-importance memory that will be eligible for cleanup
    memory_id = memory_system.add_memory("Old unimportant memory", 0.2, ["old"])

    # Since we can't directly manipulate timestamp, we'll test the cleanup function
    # with current memories and verify it works with importance threshold
    removed_ids = memory_system.cleanup_old_memories(days_threshold=0, min_importance=0.5)
    
    # Verify that the low-importance memory was removed
    assert memory_id in removed_ids
    assert memory_system.get_memory(memory_id) is None

    # Additional verification: ensure no other memories were accidentally removed
    all_memory_ids = [m.id for m in memory_system.get_all_memories()]
    assert not set(removed_ids) - {memory_id}

def test_get_all_memories(memory_system) -> None:
    """Test retrieving all memories in the system."""
    memory_system.add_memory("First memory", 0.5, ["test"])
    memory_system.add_memory("Second memory", 0.6, ["example"])

    all_memories = memory_system.get_all_memories()
    assert len(all_memories) == 2


def test_count_memories(memory_system) -> None:
    """Test counting total memories in the system."""
    memory_system.add_memory("One", 0.5, ["test"])
    memory_system.add_memory("Two", 0.6, ["example"])
    assert memory_system.count_memories() == 2


def test_get_memory_stats(memory_system) -> None:
    """Test generating memory statistics."""
    memory_system.add_memory("Important memory", 0.9, ["important"])
    memory_system.add_memory("Another important one", 0.8, ["important"])

    stats = memory_system.get_memory_stats()
    assert stats.total_memories == 2
    assert 0.8 <= stats.avg_importance <= 0.9
    assert stats.avg_access_count == 0
    assert stats.avg_age_days >= 0  # Age depends on when memories were created
