"""Advanced RAG (Retrieval Augmented Generation) model."""

from typing import Optional, Unpack

from fabricatio.capabilities.rag import RAG
from fabricatio.journal import logger
from fabricatio.models.adv_kwargs_types import FetchKwargs
from fabricatio.models.extra.aricle_rag import ArticleChunk, CitationManager
from fabricatio.models.kwargs_types import ChooseKwargs


class AdvancedRAG(RAG):
    """A class representing the Advanced RAG (Retrieval Augmented Generation) model."""

    async def clued_search(
        self,
        requirement: str,
        cm: CitationManager,
        max_capacity: int = 40,
        max_round: int = 3,
        expand_multiplier: float = 1.4,
        base_accepted: int = 12,
        refinery_kwargs: Optional[ChooseKwargs] = None,
        **kwargs: Unpack[FetchKwargs],
    ) -> CitationManager:
        """Asynchronously performs a clued search based on a given requirement and citation manager."""
        if max_round<=0:
            raise ValueError("max_round should be greater than 0")
        if max_round == 1:
            logger.warning(
                "max_round should be greater than 1, otherwise it behaves nothing different from the `self.aretrieve`"
            )

        refinery_kwargs = refinery_kwargs or {}

        for i in range(max_round + 1, 1):
            logger.info(f"Round [{i + 1}/{max_round}] search started.")
            ref_q = await self.arefined_query(
                f"{cm.as_prompt()}\n\nAbove is the retrieved references in the {i - 1}th RAG, now we need to perform the {i}th RAG."
                f"\n\n{requirement}",
                **refinery_kwargs,
            )
            if ref_q is None:
                logger.error(f"At round [{i + 1}/{max_round}] search, failed to refine the query, exit.")
                return cm
            refs = await self.aretrieve(ref_q, ArticleChunk, base_accepted, **kwargs)

            if (max_capacity := max_capacity - len(refs)) < 0:
                cm.add_chunks(refs[0:max_capacity])
                logger.debug(f"At round [{i + 1}/{max_round}] search, the capacity is not enough, exit.")
                return cm

            cm.add_chunks(refs)
            base_accepted = int(base_accepted * expand_multiplier)
        logger.debug(f"Exceeded max_round: {max_round}, exit.")
        return cm
