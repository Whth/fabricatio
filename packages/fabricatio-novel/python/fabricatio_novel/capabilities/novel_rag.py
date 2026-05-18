"""Novel RAG capabilities combining novel composition with retrieval-augmented generation."""

from fabricatio_core.utils import cfg

cfg(["rag"])
from fabricatio_rag.capabilities.rag import RAG

from fabricatio_novel.capabilities.novel import NovelCompose


class NovelComposeRAG(NovelCompose, RAG):
    """Novel composition capability extended with RAG support."""
