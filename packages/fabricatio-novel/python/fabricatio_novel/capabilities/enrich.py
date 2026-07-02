"""Novel enrichment capability: thin namespace for `EnrichChunkText` in fabricatio-novel.

This module exposes `EnrichChunkText.enrich` (LLM-guided question-answer pair
generation) as a novel-namespaced capability so actions and workflows under
`fabricatio_novel` can compose with it without depending on `fabricatio_rag`
directly at every call site.
"""

from abc import ABC

from fabricatio_rag.capabilities.enrich import EnrichChunkText


class EnrichChunkTextNovel(EnrichChunkText, ABC):
    """Novel-namespaced thin subclass of `EnrichChunkText`.

    Inherits `enrich()` and the `EnrichmentResult` model unchanged. Exists
    purely as an MRO anchor for novel-side actions that need to combine
    enrichment with retrieval-augmented storage.
    """
