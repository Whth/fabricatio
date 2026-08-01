"""Citation-aware RAG capability backed by LanceDB."""

from fabricatio_core.utils import cfg

cfg(["lancedb"])

from abc import ABC
from typing import Optional, Set

from fabricatio_core.journal import logger
from fabricatio_core.models.kwargs_types import ListingKwargs
from fabricatio_lancedb.capabilities.lancedb import LancedbFetchRAGConfig, LancedbRAG
from fabricatio_rag.capabilities.rag import RAGConfigBase

from fabricatio_typst.models.article_rag import ArticleChunk, CitationManager


class CitationSearchConfig(RAGConfigBase):
    """Configuration for iterative citation-aware RAG search."""

    max_capacity: int = 40
    """Maximum total chunks to accumulate across all rounds."""
    max_round: int = 3
    """Maximum number of search-refine iterations."""
    expand_multiplier: float = 1.4
    """Multiplier to increase accepted-chunk limit each round."""
    base_accepted: int = 12
    """Initial per-query result limit."""
    refinery_kwargs: Optional[ListingKwargs[str]] = None
    """Keyword arguments forwarded to arefined_query."""
    result_per_query: Optional[int] = None
    """Override for the LancedbFetchRAGConfig limit field."""
    table_name: Optional[str] = None
    """Override for the LancedbFetchRAGConfig table_name field."""


class CitationLancedbRAG(LancedbRAG, ABC):
    """RAG capability with citation-aware iterative search and client-side dedup."""

    async def clued_search(
        self,
        requirement: str,
        cm: CitationManager,
        config: CitationSearchConfig | None = None,
    ) -> CitationManager:
        """Iteratively refine queries, retrieve chunks, and deduplicate by citation key.

        Unlike the Milvus version, dedup is client-side: we retrieve without a
        server-side filter and exclude already-held bibtex_cite_keys after retrieval.
        """
        cnf = config or CitationSearchConfig.default()

        if cnf.max_round <= 0:
            raise ValueError("max_round should be greater than 0")
        if cnf.max_round == 1:
            logger.warn(
                "max_round should be greater than 1, otherwise it behaves nothing different from `self.afetch_document`"
            )

        refinery_kwargs = cnf.refinery_kwargs or {}
        max_capacity = cnf.max_capacity
        base_accepted = cnf.base_accepted

        for i in range(1, cnf.max_round + 1):
            logger.info(f"Round [{i}/{cnf.max_round}] search started.")
            ref_q = await self.arefined_query(
                f"{cm.as_prompt()}\n\nAbove is the retrieved references in the {i - 1}th RAG, "
                f"now we need to perform the {i}th RAG.\n\n{requirement}",
                **refinery_kwargs,
            )

            if ref_q is None:
                logger.error(f"At round [{i}/{cnf.max_round}] search, failed to refine the query, exit.")
                return cm

            conf = LancedbFetchRAGConfig(
                document_model=ArticleChunk,
                limit=cnf.result_per_query or base_accepted,
                **({"table_name": cnf.table_name} if cnf.table_name else {}),
            )
            refs = await self.afetch_document(ref_q, conf)

            # Client-side dedup: exclude already-held citations
            held_keys: Set[str] = cm.get_dedup_key_set()
            if held_keys:
                refs = [r for r in refs if r.bibtex_cite_key not in held_keys]

            if (max_capacity := max_capacity - len(refs)) < 0:
                cm.add_chunks(refs[:max_capacity])
                logger.debug(f"At round [{i}/{cnf.max_round}] search, the capacity is not enough, exit.")
                return cm

            cm.add_chunks(refs)
            base_accepted = int(base_accepted * cnf.expand_multiplier)
        logger.debug(f"Exceeded max_round: {cnf.max_round}, exit.")
        return cm
