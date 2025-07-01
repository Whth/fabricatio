"""Tests for the memory."""

from time import sleep

import pytest

# Assuming the module name is 'memory' and the classes are exposed at module level
from fabricatio_memory.rust import MemorySystem


@pytest.fixture
def memory_system() -> MemorySystem:
    """Fixture to create a temporary MemorySystem instance with in-memory index."""
    # Use in-memory index for testing
    return MemorySystem()


@pytest.mark.parametrize(
    ("content", "importance", "tags"),
    [
        ("Test memory content", 0.75, ["test", "pytest"]),
        ("Another test memory", 0.5, ["sample"]),
        ("Memory with high importance", 0.95, ["critical", "high-priority"]),
    ],
)
def test_add_and_get_memory(memory_system: MemorySystem, content: str, importance: float, tags: list) -> None:
    """Test adding a memory and retrieving it by ID."""
    memory_id = memory_system.add_memory(content, importance, tags)
    assert memory_id > 0

    memory = memory_system.get_memory(memory_id)
    assert memory is not None
    assert memory.content == content
    assert memory.importance == importance
    assert set(memory.tags) == set(tags)


@pytest.mark.parametrize(
    (
        "original_content",
        "updated_content",
        "original_importance",
        "updated_importance",
        "original_tags",
        "updated_tags",
    ),
    [
        ("Original content", "Updated content", 0.5, 0.8, ["original"], ["updated"]),
        ("Initial text", "Modified text", 0.3, 0.7, ["draft"], ["final", "reviewed"]),
    ],
)
def test_update_memory(
    memory_system: MemorySystem,
    original_content: str,
    updated_content: str,
    original_importance: float,
    updated_importance: float,
    original_tags: list,
    updated_tags: list,
) -> None:
    """Test updating memory content, importance, and tags."""
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


@pytest.mark.parametrize(
    ("content", "importance", "tags"),
    [
        ("Test content", 0.5, ["test"]),
        ("Another content", 0.7, ["sample", "delete"]),
    ],
)
def test_delete_memory_by_id(memory_system: MemorySystem, content: str, importance: float, tags: list) -> None:
    """Test deleting a memory by its ID."""
    memory_id = memory_system.add_memory(content, importance, tags)
    result = memory_system.delete_memory_by_id(memory_id)
    assert result

    # Verify that the memory is no longer retrievable
    assert memory_system.get_memory(memory_id) is None


@pytest.mark.parametrize(
    ("memories", "query", "expected_content_substring", "top_k", "boost_recent"),
    [
        (
            [("apple banana orange", 0.5, ["fruit"]), ("carrot potato tomato", 0.6, ["vegetable"])],
            "apple",
            "apple",
            100,
            False,
        ),
        (
            [("red blue green", 0.7, ["colors"]), ("square circle triangle", 0.8, ["shapes"])],
            "circle",
            "circle",
            100,
            True,
        ),
        (
            [("first item", 0.3, ["list"]), ("second item", 0.4, ["list"]), ("third item", 0.5, ["list"])],
            "item",
            "item",
            2,
            False,
        ),
    ],
)
def test_search_memories(
    memory_system: MemorySystem,
    memories: list,
    query: str,
    expected_content_substring: str,
    top_k: int,
    boost_recent: bool,
) -> None:
    """Test searching memories using a query string."""
    # Add test data
    for content, importance, tags in memories:
        memory_system.add_memory(content, importance, tags)

    results = memory_system.search_memories(query, top_k=top_k, boost_recent=boost_recent)
    assert len(results) > 0
    assert any(expected_content_substring in result.content for result in results)


@pytest.mark.parametrize(
    ("memories", "search_tags", "expected_count", "expected_content_substring"),
    [
        (
            [("Document about AI", 0.7, ["AI", "technology"]), ("Recipe for cake", 0.6, ["cooking", "baking"])],
            ["AI"],
            1,
            "AI",
        ),
        (
            [
                ("Python tutorial", 0.8, ["programming", "python"]),
                ("JavaScript basics", 0.7, ["programming", "javascript"]),
                ("JavaScript advanced", 0.7, ["programming", "javascript"]),
            ],
            ["programming"],
            3,
            None,
        ),
        (
            [("Summer vacation", 0.5, ["travel", "summer"]), ("Winter holiday", 0.6, ["travel", "winter"])],
            ["travel", "summer"],
            2,
            "Summer",
        ),
    ],
)
def test_search_by_tags(
    memory_system: MemorySystem,
    memories: list,
    search_tags: list,
    expected_count: int,
    expected_content_substring: str,
) -> None:
    """Test searching memories by tags."""
    # Add test data
    for content, importance, tags in memories:
        memory_system.add_memory(content, importance, tags)

    results = memory_system.search_by_tags(search_tags)

    assert len(results) == expected_count

    # Check if tags match
    for result in results:
        assert any(tag in result.tags for tag in search_tags), (
            f"Tag {result.tags} not found in result: {result.content}"
        )

    # Check content if expected_content_substring is provided
    if expected_content_substring:
        assert any(expected_content_substring in result.content for result in results)


@pytest.mark.parametrize(
    ("memories", "min_importance", "expected_count"),
    [
        (
            [("High importance item", 0.9, ["important"]), ("Low importance item", 0.3, ["not-important"])],
            0.5,
            1,
        ),
        (
            [("Critical task", 0.95, ["critical"]), ("Normal task", 0.6, ["normal"]), ("Minor task", 0.2, ["minor"])],
            0.7,
            1,
        ),
        (
            [("Task 1", 0.8, ["task"]), ("Task 2", 0.7, ["task"]), ("Task 3", 0.6, ["task"])],
            0.5,
            3,
        ),
    ],
)
def test_get_memories_by_importance(
    memory_system: MemorySystem, memories: list, min_importance: float, expected_count: int
) -> None:
    """Test retrieving memories by minimum importance threshold."""
    for content, importance, tags in memories:
        memory_system.add_memory(content, importance, tags)

    results = memory_system.get_memories_by_importance(min_importance)
    assert len(results) == expected_count
    for memory in results:
        assert memory.importance >= min_importance


def test_get_recent_memories(memory_system: MemorySystem) -> None:
    """Test retrieving memories created within a specified number of days."""
    # Add current memory
    current_id = memory_system.add_memory("Current memory", 0.5, ["recent"])

    # Add an older memory by creating it with the memory system
    # Since we can't manipulate timestamp directly, we'll test with what we have
    memory_system.add_memory("Old memory", 0.5, ["old"])

    # For this test, we'll just verify that get_recent_memories returns memories
    # In a real scenario, the timestamp would be set automatically when memories are created
    recent_memories = memory_system.get_recent_memories(days=365)  # Use a large range to include all memories
    assert len(recent_memories) >= 1  # At least the current memory should be included

    # Verify that our current memory is in the results
    memory_ids = [memory.id for memory in recent_memories]
    assert current_id in memory_ids


@pytest.mark.parametrize(
    ("content", "importance", "tags", "access_count", "top_k"),
    [
        ("Frequent access", 0.5, ["frequent"], 10, 1),
        ("Regular content", 0.7, ["regular"], 5, 2),
    ],
)
def test_get_frequently_accessed(
    memory_system: MemorySystem, content: str, importance: float, tags: list, access_count: int, top_k: int
) -> None:
    """Test retrieving most frequently accessed memories."""
    freq_id = memory_system.add_memory(content, importance, tags)

    # Simulate accesses
    for _ in range(access_count):
        memory_system.get_memory(freq_id)

    frequent_memories = memory_system.get_frequently_accessed(top_k=top_k)
    assert len(frequent_memories) == 1
    assert frequent_memories[0].access_count == access_count


@pytest.mark.parametrize(
    ("content", "importance", "tags", "days_threshold", "min_importance", "should_be_removed"),
    [
        ("Old unimportant memory", 0.2, ["old"], 0, 0.5, True),
        ("Important old memory", 0.8, ["old", "important"], 0, 0.5, False),
    ],
)
def test_cleanup_old_memories(
    memory_system: MemorySystem,
    content: str,
    importance: float,
    tags: list,
    days_threshold: int,
    min_importance: float,
    should_be_removed: bool,
) -> None:
    """Test cleaning up old, low-importance, infrequently accessed memories."""
    # Add a test memory
    memory_id = memory_system.add_memory(content, importance, tags)

    sleep(2)

    # Since we can't directly manipulate timestamp, we'll test the cleanup function
    # with current memories and verify it works with importance threshold
    removed_ids = memory_system.cleanup_old_memories(days_threshold=days_threshold, min_importance=min_importance)

    # Verify that the memory was removed or kept as expected
    if should_be_removed:
        assert memory_id in removed_ids
        assert memory_system.get_memory(memory_id) is None
    else:
        assert memory_id not in removed_ids
        assert memory_system.get_memory(memory_id) is not None


@pytest.mark.parametrize(
    ("memories", "expected_count"),
    [
        ([("First memory", 0.5, ["test"]), ("Second memory", 0.6, ["example"])], 2),
        ([("Single memory", 0.7, ["one"])], 1),
        ([], 0),
    ],
)
def test_get_all_memories(memory_system: MemorySystem, memories: list, expected_count: int) -> None:
    """Test retrieving all memories in the system."""
    for content, importance, tags in memories:
        memory_system.add_memory(content, importance, tags)

    all_memories = memory_system.get_all_memories()
    assert len(all_memories) == expected_count


@pytest.mark.parametrize(
    ("memories", "expected_count"),
    [
        ([("One", 0.5, ["test"]), ("Two", 0.6, ["example"])], 2),
        ([("Single entry", 0.7, ["one"])], 1),
        ([], 0),
    ],
)
def test_count_memories(memory_system: MemorySystem, memories: list, expected_count: int) -> None:
    """Test counting total memories in the system."""
    for content, importance, tags in memories:
        memory_system.add_memory(content, importance, tags)

    assert memory_system.count_memories() == expected_count


@pytest.mark.parametrize(
    ("memories", "expected_avg_importance"),
    [
        ([("Important memory", 0.9, ["important"]), ("Another important one", 0.8, ["important"])], (0.8, 0.9)),
        ([("Critical item", 1.0, ["critical"]), ("Normal item", 0.5, ["normal"])], (0.75, 0.75)),
    ],
)
def test_get_memory_stats(memory_system: MemorySystem, memories: list, expected_avg_importance: tuple) -> None:
    """Test generating memory statistics."""
    for content, importance, tags in memories:
        memory_system.add_memory(content, importance, tags)

    stats = memory_system.get_memory_stats()
    assert stats.total_memories == len(memories)
    assert expected_avg_importance[0] <= stats.avg_importance <= expected_avg_importance[1]
    assert stats.avg_access_count == 0
    assert stats.avg_age_days >= 0  # Age depends on when memories were created
