"""RAG-extended scene composition: retrieve raw writing style references for sealed stories."""

from abc import ABC
from typing import Unpack

from fabricatio_core import logger
from fabricatio_core.decorators import logging_exec_time
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import cfg

cfg(["lancedb"])

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG

from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.models.context.chapter import ChapterContext
from fabricatio_novel.models.context.rag import RagRetrieval, RagStoryContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig


class RAGCompose(ChapterCompose, LancedbRAG[WritingStyleDocument, LancedbAddRAGConfig, WritingStyleFetchConfig], ABC):
    """Novel composition capabilities extended with writing style retrieval.

    Retrieval settings are sealed onto a dedicated :class:`~fabricatio_novel.models.context.rag.RagStoryContext`
    subclass — the standard context tree carries no retrieval state.
    :meth:`plan_stories_phase` seals each chapter's stories right after they
    are planned; retrieved documents are held as the story's retrieved styles
    and render through ``prefixed_header_entry()`` into every scene write
    prompt's prefix-cacheable region. The next story's prefix cannot contain
    them: stories forward only their scenes' entries. Once a story's scenes are
    fully written, :meth:`~fabricatio_novel.models.context.rag.RagStoryContext.prefixed_header_entry`
    stops rendering them into later walks (illustration proposals included)
    while keeping the raw texts for scoring and audit.
    """

    rag_query: str = ""
    """Custom query guideline for writing style retrieval; empty uses the story description."""

    rag_limit: int = 15
    """Reference documents kept per story."""

    async def plan_stories_phase(
        self,
        ctx: ChapterContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan the chapter's stories, then seal them with the retrieval settings.

        Returns:
            bool: True when the stories are planned and sealed; False on planning failure.
        """
        if not await super().plan_stories_phase(ctx, send_to, **kwargs):
            return False
        rag = RagRetrieval(query=self.rag_query, limit=self.rag_limit)
        ctx.child_contexts = [RagStoryContext.seal(story, rag) for story in ctx.child_contexts]
        return True

    @logging_exec_time
    async def prepare_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Retrieve raw writing style references for a sealed story before its scenes are planned.

        Unsealed story contexts carry no retrieval settings and are skipped.
        The documents are held as the story's retrieved styles and render as
        one shared prefix entry into every scene write prompt; no condensation
        is applied.
        """
        await super().prepare_story(ctx, send_to, **kwargs)
        if not isinstance(ctx, RagStoryContext):
            return
        docs = await self._fetch_style_docs(ctx, send_to=send_to, **kwargs)
        ctx.add_retrieved_styles([doc.as_prompt() for doc in docs])
        logger.debug(f"Retrieved {len(docs)} style reference(s) for story '{ctx.title}'")

    async def _fetch_style_docs(
        self,
        ctx: RagStoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[WritingStyleDocument]:
        """Fetch the story's style references through decomposed multi-head queries.

        The story description (plus the optional query guideline) is decomposed
        into as many sub-queries as the model proposes; every head is searched
        independently and the store fuses the per-head rankings with a round-robin
        fair share, so no single phrasing can dominate the candidate set. Heads
        beyond :attr:`rag_limit` are dropped — the budget caps documents, so no
        head past it can earn a slot. Nothing reranks the fused set: fusion already
        balances the heads, and reranking a set that has already been truncated to
        the limit could only permute it.

        An answer with fewer than two heads is not a decomposition, so it is
        discarded for the raw question: the model either restated the input or
        declined the request, and searching such a lone head would hand the whole
        document budget to one phrasing. A refusal needs no detection of its own —
        it arrives as exactly that one-head answer.
        """
        question = "\n".join(part for part in (ctx.description, ctx.rag.query) if part)
        if not question:
            return []
        queries = await self.arefined_query(question, send_to=send_to, **kwargs) or []
        if len(queries) <= 1:
            logger.warn(
                f"Query decomposition of story '{ctx.title}' gave {len(queries)} head(s); searching the raw query"
            )
            queries = [question]
        config = WritingStyleFetchConfig(limit=ctx.rag.limit)
        docs = await self.afetch_document(queries[: config.limit], config)
        docs = [doc for doc in docs if doc.as_prompt().strip()]
        docs = docs[: config.limit]
        logger.info(
            f"Retrieved {len(docs)} writing style reference(s) for story '{ctx.title}' via {len(queries)} head(s)"
        )
        return docs
