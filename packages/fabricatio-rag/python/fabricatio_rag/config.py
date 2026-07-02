"""Module containing configuration classes for fabricatio-rag."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass
class RagConfig:
    """Configuration for fabricatio-rag."""

    # Query and Search Templates
    refined_query_template: str = "built-in/refined_query"
    """The name of the refined query template which will be used to refine a query."""

    precise_chunk_template: str = "built-in/precise_chunk"
    """"""

    enrich_qa_template: str = "built-in/enrich_qa"
    """Template for generating question-answer pairs from text chunks."""

    mini_chunk_size: int = 128


rag_config = CONFIG.load("rag", RagConfig)
__all__ = ["rag_config"]
