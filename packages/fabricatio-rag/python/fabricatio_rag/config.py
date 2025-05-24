"""Module containing configuration classes for fabricatio-rag."""
from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass
class RagConfig:
    """Configuration for fabricatio-rag."""
    # Query and Search Templates
    refined_query_template: str
    """The name of the refined query template which will be used to refine a query."""



rag_config = CONFIG.load("rag",  RagConfig)
__all__ = [
    "rag_config"
]
