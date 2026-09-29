"""Citation-aware composition: writing subsections against the article-essence corpus."""

from abc import ABC
from typing import Unpack

from fabricatio_core.utils import cfg

cfg(["lancedb"])

from fabricatio_core import logger
from fabricatio_core.models.kwargs_types import ListingKwargs, LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import ok
from pydantic import PositiveInt

from fabricatio_typst.capabilities.citation_rag import CitationLancedbRAG, CitationSearchConfig
from fabricatio_typst.capabilities.subsection import SubsectionCompose, clean_prose
from fabricatio_typst.models.article_main import split_paragraphs
from fabricatio_typst.models.article_rag import CitationManager
from fabricatio_typst.models.context.subsection import SubsectionContext
from fabricatio_typst.rust import convert_all_tex_math, fix_misplaced_labels


class CitationSubsectionCompose[CTX: SubsectionContext](SubsectionCompose[CTX], CitationLancedbRAG, ABC):
    """Writes a subsection's prose from retrieved references and cites them inline.

    Retrieval runs before the write, one ``clued_search`` per subsection seeded with the
    running text and the subsection's own plan; the model sees the numbered references
    and writes ``[[n]]`` markers, which the manager rewrites into typst ``@cite`` notation
    on the paragraphs they support.
    """

    ref_limit: int = 35
    """The number of references one subsection may accept across the search rounds."""
    search_increment_multiplier: float = 1.6
    """The multiplier applied to the accepted-reference budget on every RAG round."""
    result_per_query: PositiveInt = 4
    """The number of chunks each refined query retrieves."""
    query_model: ListingKwargs[str] | None = None
    """The keyword arguments used to refine the search queries."""
    table_name: str | None = None
    """The LanceDB table holding the reference corpus; the default table is used when unset."""

    async def search_references(self, ctx: CTX, **kwargs: Unpack[LLMKwargs]) -> CitationManager:
        """Retrieve the references that support this subsection.

        The search requirement is the running text plus the subsection's own plan, so the
        queries stay grounded on what the article has established and what this
        subsection still owes.
        """
        aims = "".join(f"- {aim}\n" for aim in ctx.plan.aims) if ctx.plan is not None else ""
        requirement = (
            f"{ctx.prefix_log.render()}\n\nAbove is the article so far.\n"
            f"# Subsection to write\n{ctx.title}\n{ctx.description}\n{aims}"
        )
        cm = CitationManager()
        await self.clued_search(
            requirement,
            cm,
            config=CitationSearchConfig(
                base_accepted=self.ref_limit,
                expand_multiplier=self.search_increment_multiplier,
                result_per_query=self.result_per_query,
                refinery_kwargs=self.query_model,
                table_name=self.table_name,
            ),
        )
        logger.info(f"Retrieved {len(cm.article_chunks)} reference chunk(s) for subsection '{ctx.title}'")
        return cm

    def prepare_rag_requirement(self, ctx: CTX, cm: CitationManager, **kwargs: Unpack[LLMKwargs]) -> str:
        """Render the write requirement with the retrieved references attached."""
        return self.prepare_subsection_requirement(ctx, references=cm.as_prompt(), **kwargs)

    async def generate_subsection_context(
        self,
        ctx: CTX,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> CTX:
        """Retrieve, then write the prose with inline citations and typst math.

        The label and math fixups run before the citation pass, so the ``[[n]]`` markers
        the model misplaced are repaired before they are rewritten.
        """
        cm = await self.search_references(ctx, **kwargs)
        requirement = self.prepare_rag_requirement(ctx, cm, **kwargs)
        logger.info(f"Writing subsection '{ctx.title}' ({ctx.expected_word_count} words expected)")
        raw = clean_prose(
            ok(await self.aask(requirement, send_to, **kwargs), f"Subsection '{ctx.title}' came back empty"),
        )
        raw = fix_misplaced_labels(raw)
        raw = convert_all_tex_math(raw)
        return ctx.set_content("\n\n".join(cm.apply(block) for block in split_paragraphs(raw)))


__all__ = ["CitationSubsectionCompose"]
