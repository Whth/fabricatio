from functools import lru_cache

from fabricatio_lancedb.config import lancedb_config
from fabricatio_lancedb.rust import VectorStoreService


@lru_cache
def get_service(uri: str = lancedb_config.database_uri) -> VectorStoreService:
    return VectorStoreService.connect(uri)
