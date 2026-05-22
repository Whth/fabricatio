"""Module for initializing and providing a cached LanceDB vector store service."""

from fabricatio_lancedb.config import lancedb_config
from fabricatio_lancedb.rust import VectorStoreService

_CONNECTION_CACHE: dict[str, VectorStoreService] = {}


async def get_service(uri: str = lancedb_config.database_uri) -> VectorStoreService:
    """Return a cached VectorStoreService connected to the given URI."""
    if uri in _CONNECTION_CACHE:
        return _CONNECTION_CACHE[uri]

    service = await VectorStoreService.connect(uri)
    _CONNECTION_CACHE[uri] = service
    return service
