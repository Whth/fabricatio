"""LLM-driven text enrichment: generate question-answer pairs from source text."""

from abc import ABC
from typing import List, overload

from fabricatio_core import TEMPLATE_MANAGER
from fabricatio_core.capabilities.propose import Propose

from fabricatio_rag.config import rag_config
from fabricatio_rag.models.qa import EnrichmentResult


class EnrichChunkText(Propose, ABC):
    """Generate question-answer pairs from text chunks via LLM enrichment."""

    @overload
    async def enrich(self, enrich_guideline: str, chunk: str) -> EnrichmentResult: ...

    @overload
    async def enrich(self, enrich_guideline: str, chunk: List[str]) -> List[EnrichmentResult]: ...

    async def enrich(
        self,
        enrich_guideline: str,
        chunk: str | List[str],
    ) -> EnrichmentResult | List[EnrichmentResult]:
        """Generate QAPairs from text chunk(s) guided by enrichment instructions.

        Args:
            enrich_guideline: Free-form NL describing what kinds of questions
                to generate (e.g. "factual recall", "conceptual", "multi-hop").
            chunk: Single string or list of strings to enrich.

        Returns:
            For a single str: an EnrichmentResult with qa_pairs for that chunk.
            For a list of str: a list of EnrichmentResults, one per input chunk,
            preserving input order.
        """
        was_str = isinstance(chunk, str)
        chunks = [chunk] if was_str else chunk

        render_inputs = [{"enrich_guideline": enrich_guideline, "chunk": c} for c in chunks]
        requirements = TEMPLATE_MANAGER.render_template(rag_config.enrich_qa_template, render_inputs)

        results = await self.propose(EnrichmentResult, requirements)
        return results[0] if was_str else results
