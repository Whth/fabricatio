"""Module containing configuration classes for fabricatio-rag."""
from dataclasses import dataclass
from typing import Optional

from fabricatio_core import CONFIG
from fabricatio_core.rust import SecretStr


@dataclass
class RagConfig:
    """Configuration for fabricatio-rag."""
    # Query and Search Templates
    refined_query_template: str
    """The name of the refined query template which will be used to refine a query."""

    milvus_uri: Optional[str]
    """The URI of the Milvus server."""

    milvus_timeout: Optional[float]
    """The timeout of the Milvus server in seconds."""

    milvus_token: Optional[SecretStr]
    """The token for Milvus authentication."""

    milvus_dimensions: Optional[int]
    """The dimensions for Milvus vectors."""



rag_config = CONFIG.load("rag",  RagConfig)
__all__ = [
    "rag_config"
]
