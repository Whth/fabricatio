"""This module defines the `ChunkKwargs` TypedDict, which is used to hold configuration parameters for chunking operations."""

from typing import NotRequired, TypedDict


class ChunkKwargs(TypedDict):
    """Configuration parameters for chunking operations."""

    max_chunk_size: int
    max_overlapping_rate: NotRequired[float]
