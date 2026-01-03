"""Tests for the memory."""

import uuid

import pytest

# Assuming the module name is 'memory' and the classes are exposed at module level
from fabricatio_memory.rust import MemoryService, MemoryStore


@pytest.fixture(scope="session")
def memory_service(tmp_path_factory: pytest.TempPathFactory) -> MemoryService:
    """Fixture to create a temporary MemorySystem instance with in-memory index."""
    return MemoryService(tmp_path_factory.mktemp("memory_root"))


@pytest.fixture
def store(memory_service: MemoryService) -> MemoryStore:
    """Fixture to create a MemoryStore instance."""
    return memory_service.get_store(uuid.uuid7().hex)


@pytest.mark.parametrize(
    ("content", "importance", "tags"),
    [
        ("Test memory content", 75, ["test", "pytest"]),
        ("Another test memory", 50, ["sample"]),
        ("Memory with high importance", 95, ["critical", "high-priority"]),
    ],
)
def test_add_and_get_memory(store: MemoryStore, content: str, importance: int, tags: list) -> None:
    """Test adding a memory and retrieving it by ID."""
    memory_id = store.add_memory(content, importance, tags)
    assert memory_id
    store.write()  # Ensure data is persisted before reading
    memory = store.get_memory(memory_id)
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
        ("Original content", "Updated content", 50, 80, ["original"], ["updated"]),
        ("Initial text", "Modified text", 30, 70, ["draft"], ["final", "reviewed"]),
    ],
)
def test_update_memory(
    store: MemoryStore,
    original_content: str,
    updated_content: str,
    original_importance: int,
    updated_importance: int,
    original_tags: list,
    updated_tags: list,
) -> None:
    """Test updating memory content, importance, and tags."""
    memory_id = store.add_memory(original_content, original_importance, original_tags)
    store.write()  # Persist initial memory

    # Update all fields
    success = store.update_memory(memory_id, content=updated_content, importance=updated_importance, tags=updated_tags)
    assert success
    store.write()  # Persist update

    memory = store.get_memory(memory_id)
    assert memory is not None
    assert memory.content == updated_content
    assert memory.importance == updated_importance
    assert set(memory.tags) == set(updated_tags)


@pytest.mark.parametrize(
    ("content", "importance", "tags"),
    [
        ("Test content", 50, ["test"]),
        ("Another content", 70, ["sample", "delete"]),
    ],
)
def test_delete_memory(store: MemoryStore, content: str, importance: int, tags: list) -> None:
    """Test deleting a memory by its ID."""
    memory_id = store.add_memory(content, importance, tags)
    store.write()  # Persist before deletion
    result = store.delete_memory(memory_id)
    assert result
    store.write()  # Persist deletion

    # Verify that the memory is no longer retrievable
    assert store.get_memory(memory_id) is None


@pytest.mark.parametrize(
    ("memories", "query", "expected_content_substring", "top_k", "boost_recent"),
    [
        (
            [("apple banana orange", 50, ["fruit"]), ("carrot potato tomato", 60, ["vegetable"])],
            "apple",
            "apple",
            100,
            False,
        ),
        (
            [("red blue green", 70, ["colors"]), ("square circle triangle", 80, ["shapes"])],
            "circle",
            "circle",
            100,
            True,
        ),
        (
            [("first item", 30, ["list"]), ("second item", 40, ["list"]), ("third item", 50, ["list"])],
            "item",
            "item",
            2,
            False,
        ),
    ],
)
def test_search_memories(
    store: MemoryStore,
    memories: list,
    query: str,
    expected_content_substring: str,
    top_k: int,
    boost_recent: bool,
) -> None:
    """Test searching memories using a query string."""
    # Add test data
    for content, importance, tags in memories:
        store.add_memory(content, importance, tags)
    store.write()  # Persist all memories before search

    results = store.search_memories(query, top_k=top_k, boost_recent=boost_recent)
    assert len(results) > 0
    assert any(expected_content_substring in result.content for result in results)


@pytest.mark.parametrize(
    ("memories", "search_tags", "expected_count", "expected_content_substring"),
    [
        (
            [("Document about AI", 70, ["AI", "technology"]), ("Recipe for cake", 60, ["cooking", "baking"])],
            ["AI"],
            1,
            "AI",
        ),
        (
            [
                ("Python tutorial", 80, ["programming", "python"]),
                ("JavaScript basics", 70, ["programming", "javascript"]),
                ("JavaScript advanced", 70, ["programming", "javascript"]),
            ],
            ["programming"],
            3,
            None,
        ),
        (
            [("Summer vacation", 50, ["travel", "summer"]), ("Winter holiday", 60, ["travel", "winter"])],
            ["travel", "summer"],
            2,
            "Summer",
        ),
    ],
)
def test_search_by_tags(
    store: MemoryStore,
    memories: list,
    search_tags: list,
    expected_count: int,
    expected_content_substring: str,
) -> None:
    """Test searching memories by tags."""
    # Add test data
    for content, importance, tags in memories:
        store.add_memory(content, importance, tags)
    store.write()  # Persist before tag search

    results = store.search_by_tags(search_tags)

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
            [("High importance item", 90, ["important"]), ("Low importance item", 30, ["not-important"])],
            50,
            1,
        ),
        (
            [("Critical task", 95, ["critical"]), ("Normal task", 60, ["normal"]), ("Minor task", 20, ["minor"])],
            70,
            1,
        ),
        (
            [("Task 1", 80, ["task"]), ("Task 2", 70, ["task"]), ("Task 3", 60, ["task"])],
            50,
            3,
        ),
    ],
)
def test_get_memories_by_importance(
    store: MemoryStore, memories: list, min_importance: int, expected_count: int
) -> None:
    """Test retrieving memories by minimum importance threshold."""
    for content, importance, tags in memories:
        store.add_memory(content, importance, tags)
    store.write()  # Persist before filtering

    results = store.get_memories_by_importance(min_importance)
    assert len(results) == expected_count
    for memory in results:
        assert memory.importance >= min_importance


def test_get_recent_memories(store: MemoryStore) -> None:
    """Test retrieving memories created within a specified number of days."""
    # Add current memory
    current_id = store.add_memory("Current memory", 50, ["recent"])
    store.add_memory("Old memory", 50, ["old"])
    store.write()  # Persist both

    recent_memories = store.get_recent_memories(days=365)  # Use a large range to include all memories
    assert len(recent_memories) >= 1  # At least the current memory should be included

    # Verify that our current memory is in the results
    memory_ids = [memory.uuid for memory in recent_memories]
    assert current_id in memory_ids


@pytest.mark.parametrize(
    ("content", "importance", "tags", "access_count", "top_k"),
    [
        ("Frequent access", 50, ["frequent"], 10, 1),
        ("Regular content", 70, ["regular"], 5, 2),
    ],
)
def test_get_frequently_accessed(
    store: MemoryStore, content: str, importance: int, tags: list, access_count: int, top_k: int
) -> None:
    """Test retrieving most frequently accessed memories."""
    freq_id = store.add_memory(content, importance, tags)
    store.write()  # Must persist before accesses count reliably (assuming access tracking requires read from store)

    # Simulate accesses
    for _ in range(access_count):
        store.get_memory(freq_id, write=True)

    # Re-persist to capture access count if it's tracked in-memory and written on write()

    frequent_memories = store.get_frequently_accessed(top_k=top_k)
    assert len(frequent_memories) == 1
    assert frequent_memories[0].access_count == access_count


@pytest.mark.parametrize(
    ("memories", "expected_count"),
    [
        ([("One", 50, ["test"]), ("Two", 60, ["example"])], 2),
        ([("Single entry", 70, ["one"])], 1),
        ([], 0),
    ],
)
def test_count_memories(store: MemoryStore, memories: list, expected_count: int) -> None:
    """Test counting total memories in the system."""
    for content, importance, tags in memories:
        store.add_memory(content, importance, tags)
    store.write()  # Ensure count reflects persisted state

    assert store.count_memories() == expected_count


@pytest.mark.parametrize(
    ("memories", "expected_avg_importance"),
    [
        ([("Important memory", 90, ["important"]), ("Another important one", 80, ["important"])], (85, 85)),
        ([("Critical item", 100, ["critical"]), ("Normal item", 50, ["normal"])], (75, 75)),
    ],
)
def test_get_memory_stats(store: MemoryStore, memories: list, expected_avg_importance: tuple) -> None:
    """Test generating memory statistics."""
    for content, importance, tags in memories:
        store.add_memory(content, importance, tags)
    store.write()  # Persist before stats

    stats = store.stats()
    assert stats.total_memories == len(memories)
    expected_avg = expected_avg_importance[0]
    assert abs(stats.avg_importance - expected_avg) < 1e-6  # exact match for integers
    assert stats.avg_access_count == 0
    assert stats.avg_age_days >= 0  # Age depends on when memories were created
