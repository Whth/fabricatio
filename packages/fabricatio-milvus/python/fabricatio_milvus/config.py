"""Module containing configuration classes for fabricatio-milvus."""

from dataclasses import dataclass
from typing import Optional

from fabricatio_core import CONFIG
from pydantic import SecretStr


@dataclass(frozen=True)
class MilvusConfig:
    """Configuration for fabricatio-milvus."""

    milvus_uri: Optional[str] = None
    """The URI of the Milvus server."""

    milvus_timeout: Optional[float] = None
    """The timeout of the Milvus server in seconds."""

    milvus_token: Optional[SecretStr] = None
    """The token for Milvus authentication."""

    milvus_dimensions: Optional[int] = None
    """The dimensions for Milvus vectors."""


milvus_config = CONFIG.load("milvus", MilvusConfig)

__all__ = ["milvus_config"]
