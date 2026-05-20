"""Novel RAG capabilities combining novel composition with retrieval-augmented generation."""

from fabricatio_core.utils import cfg

cfg(["lancedb"])
from fabricatio_lancedb.capabilities.lancedb import LancedbRAG

from fabricatio_novel.capabilities.novel import NovelCompose


class NovelComposeRAG(NovelCompose, LancedbRAG):
    """Novel composition capability extended with RAG support."""

    # TODO impl
