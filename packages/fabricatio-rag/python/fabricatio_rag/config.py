"""Module containing configuration classes for fabricatio-rag."""

from dataclasses import dataclass
from typing import Optional

from fabricatio_core import CONFIG
from fabricatio_core.rust import SecretStr


@dataclass
class RagConfig:
    """Configuration for fabricatio-rag."""

    # Query and Search Templates
    refined_query_template: str = "refined_query"
    """The name of the refined query template which will be used to refine a query."""

    milvus_uri: Optional[str] = None
    """The URI of the Milvus server."""

    milvus_timeout: Optional[float] = None
    """The timeout of the Milvus server in seconds."""

    milvus_token: Optional[SecretStr] = None
    """The token for Milvus authentication."""

    milvus_dimensions: Optional[int] = None
    """The dimensions for Milvus vectors."""


rag_config = CONFIG.load("rag", RagConfig)
__all__ = ["rag_config"]
