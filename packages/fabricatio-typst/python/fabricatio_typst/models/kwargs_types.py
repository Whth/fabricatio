from typing import NotRequired, TypedDict


class ChunkKwargs(TypedDict):
    """Configuration parameters for chunking operations."""

    max_chunk_size: int
    max_overlapping_rate: NotRequired[float]
