"""Novel enrichment capability: QA pairs from reference chunks (fabricatio-rag)."""

from abc import ABC

from fabricatio_rag.capabilities.enrich import EnrichChunkText


class EnrichCompose(EnrichChunkText, ABC):
    """Novel-namespaced enrichment capability."""
