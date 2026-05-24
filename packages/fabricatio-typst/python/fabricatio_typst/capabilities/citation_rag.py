from fabricatio_core.utils import cfg

cfg(["lancedb"])

"""Citation-aware RAG capability backed by LanceDB."""

from abc import ABC
from typing import Optional, Set

from fabricatio_core.journal import logger
from fabricatio_core.models.kwargs_types import ListStringKwargs
from fabricatio_lancedb.capabilities.lancedb import LancedbRAG

from fabricatio_typst.models.article_rag import ArticleChunk, CitationManager


class CitationLancedbRAG(LancedbRAG, ABC):
    """RAG capability with citation-aware iterative search and client-side dedup."""

    async def clued_search(
        self,
        requirement: str,
        cm: CitationManager,
        max_capacity: int = 40,
        max_round: int = 3,
        expand_multiplier: float = 1.4,
        base_accepted: int = 12,
        refinery_kwargs: Optional[ListStringKwargs] = None,
        result_per_query: Optional[int] = None,
        table_name: Optional[str] = None,
    ) -> CitationManager:
        """Iteratively refine queries, retrieve chunks, and deduplicate by citation key.

        Unlike the Milvus version, dedup is client-side: we retrieve without a
        server-side filter and exclude already-held bibtex_cite_keys after retrieval.
        """
        if max_round <= 0:
            raise ValueError("max_round should be greater than 0")
        if max_round == 1:
            logger.warn(
                "max_round should be greater than 1, otherwise it behaves nothing different from `self.aretrieve`"
            )

        refinery_kwargs = refinery_kwargs or {}

        for i in range(1, max_round + 1):
            logger.info(f"Round [{i}/{max_round}] search started.")
            ref_q = await self.arefined_query(
                f"{cm.as_prompt()}\n\nAbove is the retrieved references in the {i - 1}th RAG, "
                f"now we need to perform the {i}th RAG.\n\n{requirement}",
                **refinery_kwargs,
            )

            if ref_q is None:
                logger.error(f"At round [{i}/{max_round}] search, failed to refine the query, exit.")
                return cm

            refs = await self.aretrieve(
                ref_q,
                ArticleChunk,
                base_accepted,
                table_name=table_name,
                result_per_query=result_per_query,
            )

            # Client-side dedup: exclude already-held citations
            held_keys: Set[str] = cm.get_dedup_key_set()
            if held_keys:
                refs = [r for r in refs if r.bibtex_cite_key not in held_keys]

            if (max_capacity := max_capacity - len(refs)) < 0:
                cm.add_chunks(refs[:max_capacity])
                logger.debug(f"At round [{i}/{max_round}] search, the capacity is not enough, exit.")
                return cm

            cm.add_chunks(refs)
            base_accepted = int(base_accepted * expand_multiplier)
        logger.debug(f"Exceeded max_round: {max_round}, exit.")
        return cm
