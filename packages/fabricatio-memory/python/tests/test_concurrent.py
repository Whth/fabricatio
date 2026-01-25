"""Tests for concurrent access to the same MemoryStore."""

import threading
import time
import uuid
from pathlib import Path
from typing import List

import pytest
from fabricatio_memory.rust import MemoryService


@pytest.fixture
def shared_memory_service(tmp_path: Path) -> MemoryService:
    """MemoryService with small cache to stress concurrency."""
    return MemoryService(tmp_path.as_posix(), cache_size=5)


def worker_add_memories(
    memory_service: MemoryService,
    store_name: str,
    thread_id: int,
    num_memories: int,
    results: List[str],
    errors: List[Exception],
) -> None:
    """Worker function that adds memories to a shared store."""
    store = memory_service.get_store(store_name)
    thread_results = []
    for i in range(num_memories):
        content = f"Thread-{thread_id}-Memory-{i}-{uuid.uuid4().hex}"
        mem_id = store.add_memory(content, importance=50, tags=[f"thread_{thread_id}"])
        thread_results.append(mem_id)
        # Optional: small delay to increase interleaving
        time.sleep(0.001)
    # Write at end to reduce I/O pressure (or write=True per add if needed)
    store.write()
    results.extend(thread_results)


def test_concurrent_writers_on_same_store(shared_memory_service: MemoryService) -> None:
    """Test that multiple threads writing to the SAME store do not corrupt the index.

    This indirectly verifies that only one IndexWriter exists per store,
    and that writes are properly synchronized.
    """
    store_name = "concurrent_test_store"
    num_threads = 5
    memories_per_thread = 10

    all_memory_ids: List[str] = []
    errors: List[Exception] = []

    threads = []
    for tid in range(num_threads):
        thread = threading.Thread(
            target=worker_add_memories,
            args=(shared_memory_service, store_name, tid, memories_per_thread, all_memory_ids, errors),
            name=f"Worker-{tid}",
        )
        threads.append(thread)
        thread.start()

    for t in threads:
        t.join()

    # Assert no errors occurred (e.g., no index corruption, no lock issues)
    assert len(errors) == 0, f"Errors during concurrent access: {errors}"

    # Now retrieve the store again and verify all memories exist
    final_store = shared_memory_service.get_store(store_name)
    total_count = final_store.count_memories()
    expected_total = num_threads * memories_per_thread

    assert total_count == expected_total, (
        f"Expected {expected_total} memories, but found {total_count}. "
        "This suggests writes were lost or index is corrupted."
    )

    # Optional: Verify each memory can be retrieved
    for mem_id in all_memory_ids:
        memory = final_store.get_memory(mem_id)
        assert memory is not None, f"Memory {mem_id} not found after concurrent writes"


def test_concurrent_reads_and_writes(shared_memory_service: MemoryService) -> None:
    """Test mixed read/write workload on the same store."""
    store_name = "mixed_rw_store"
    store = shared_memory_service.get_store(store_name)

    # Add initial memory
    initial_id = store.add_memory("initial", 50, ["base"])
    store.write()

    def reader_worker(results: list, errors: list) -> None:
        try:
            s = shared_memory_service.get_store(store_name)
            for _ in range(20):
                mem = s.get_memory(initial_id)
                if mem:
                    results.append(mem.content)
                time.sleep(0.001)
        except OSError as e:
            errors.append(e)

    def writer_worker(errors: list) -> None:
        try:
            s = shared_memory_service.get_store(store_name)
            for i in range(5):
                s.add_memory(f"write-{i}", 50, ["concurrent"])
                s.write()
                time.sleep(0.005)
        except OSError as e:
            errors.append(e)

    read_results: List[str] = []
    errors: List[Exception] = []

    reader = threading.Thread(target=reader_worker, args=(read_results, errors))
    writer = threading.Thread(target=writer_worker, args=(errors,))

    reader.start()
    writer.start()

    reader.join()
    writer.join()

    assert len(errors) == 0, f"Errors in mixed RW: {errors}"
    assert len(read_results) > 0, "No reads succeeded"

    # Final count should be 1 (initial) + 5 (writes)
    final_count = shared_memory_service.get_store(store_name).count_memories()
    assert final_count == 6
