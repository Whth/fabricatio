"""Module for initializing and providing a cached LanceDB vector store service."""

from functools import lru_cache

from fabricatio_lancedb.config import lancedb_config
from fabricatio_lancedb.rust import VectorStoreService


@lru_cache
def get_service(uri: str = lancedb_config.database_uri) -> VectorStoreService:
    """Return a cached VectorStoreService connected to the given URI."""
    return VectorStoreService.connect(uri)
