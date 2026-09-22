"""RAG-extended composition: writing style references for the novel plan, its chapters and the sealed stories."""

from abc import ABC
from typing import Unpack

from fabricatio_core import logger
from fabricatio_core.decorators import logging_exec_time
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import SMOL, TASK
from fabricatio_core.utils import cfg, wrap_in_block

cfg(["lancedb"])

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG

from fabricatio_novel.capabilities.chapter import ChapterCompose
from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.context.chapter import ChapterContext, RagChapterContext
from fabricatio_novel.models.context.novel import NovelContext, RagNovelContext
from fabricatio_novel.models.context.rag import RagRetrieval, RagStoryContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig


class RAGStyleFetch(LancedbRAG[WritingStyleDocument, LancedbAddRAGConfig, WritingStyleFetchConfig], ABC):
    """Writing style retrieval shared by the RAG-bound levels: the settings and the multi-head search.

    Which text is searched, and where the fetched documents end up, is the level's
    own business: :class:`RAGNovelCompose` searches the outline for the prompts
    that plan the novel and its chapters, :class:`RAGChapterCompose` searches a
    story's description for its scene writes.
    """

    rag_query: str = ""
    """Custom query guideline for style retrieval, combined with the level's own text; empty searches that text alone."""

    rag_limit: int = 15
    """Reference documents kept per retrieval level."""

    async def _fetch_style_docs(
        self,
        source: str,
        rag: RagRetrieval,
        label: str,
        send_to: str | None = SMOL,
        **kwargs: Unpack[LLMKwargs],
    ) -> list[WritingStyleDocument]:
        """Fetch one level's style references through decomposed multi-head queries.

        The level's own text (plus the optional query guideline) is decomposed into
        as many sub-queries as the model proposes. Every head is searched independently
        and the store fuses the per-head rankings with a round-robin fair share, so no
        single phrasing can dominate the candidate set. Heads beyond the level's limit
        are dropped — the budget caps documents, so no head past it can earn a slot.
        Nothing reranks the fused set: fusion already balances the heads, and reranking
        a set that has already been truncated to the limit could only permute it.

        The decomposition rides the ``SMOL`` agent variant, :meth:`arefined_query`'s
        own default: turning a level's text into search heads is mechanical work that
        need not follow the run's writing group, and no other call here reaches a
        completion model — the search is embedding plus fused ranking. A caller that
        wants the refinement elsewhere passes the group it wants; the pipeline's own
        levels leave the default be, so the run's ``send_to`` never reaches it.

        An answer with fewer than two heads is not a decomposition, so it is
        discarded for the raw question: the model either restated the input or
        declined the request, and searching such a lone head would hand the whole
        document budget to one phrasing. A refusal needs no detection of its own —
        it arrives as exactly that one-head answer.

        ``label`` names the level in the logs (``the novel``, ``story 'St1'``),
        since the search text alone does not say which prompt it feeds.
        """
        question = "\n".join(part for part in (source, rag.query) if part)
        if not question:
            return []
        queries = await self.arefined_query(question, send_to=send_to, **kwargs) or []
        if len(queries) <= 1:
            logger.warn(f"Query decomposition of {label} gave {len(queries)} head(s); searching the raw query")
            queries = [question]
        config = WritingStyleFetchConfig(limit=rag.limit)
        docs = await self.afetch_document(queries[: config.limit], config)
        docs = [doc for doc in docs if doc.as_prompt().strip()]
        docs = docs[: config.limit]
        logger.info(f"Retrieved {len(docs)} writing style reference(s) for {label} via {len(queries)} head(s)")
        return docs


class RAGNovelCompose(NovelCompose, RAGStyleFetch, ABC):
    """Novel-level RAG composition: the root's references are fetched before the novel and its chapters are planned.

    The seal happens in :meth:`before_compose_novel_context` — the point both the
    staged pipeline (through its init stage) and the programmatic chain (through
    ``compose_novel``) enter a novel at — so the metadata proposal, the chapter
    plans and every stage snapshot see the same root: a
    :class:`~fabricatio_novel.models.context.novel.RagNovelContext` whose
    ``retrieved_styles`` render into those two planning prompts and into nothing
    else. Planning the chapters then promotes each created chapter to
    :class:`~fabricatio_novel.models.context.chapter.RagChapterContext`, so a run
    stays RAG-typed from the root down and every snapshot of it reloads with the
    references that stage saw.
    """

    async def retrieve_novel_styles(
        self,
        ctx: NovelContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> RagNovelContext:
        """Seal the root with the retrieval settings and fetch the references its planning prompts render.

        The novel is planned and its chapters are planned from the outline, so that
        is the text the search reads — the description does not exist yet when the
        run retrieves. The outline is wrapped exactly as the planning prompts
        render it, so this first call of the run primes the same head every
        planning call afterwards reuses.
        """
        sealed = RagNovelContext.seal(ctx, RagRetrieval(query=self.rag_query, limit=self.rag_limit))
        source = "\n\n".join(
            part for part in (sealed.skill_section(), wrap_in_block(sealed.outline, title="Novel Outline")) if part
        )
        docs = await self._fetch_style_docs(source, sealed.rag, "the novel", **kwargs)
        sealed.add_retrieved_styles([doc.as_prompt() for doc in docs])
        logger.debug(f"Retrieved {len(docs)} style reference(s) for the novel root")
        return sealed

    async def before_compose_novel_context(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> RagNovelContext:
        """Seal the root with the retrieval settings and adopt the references before anything is planned.

        Returns:
            RagNovelContext: The sealed root — the context class every root of a
                RAG run carries, so the planning prompts and every snapshot see
                its references.
        """
        return await self.retrieve_novel_styles(ctx, **kwargs)

    async def plan_chapters_phase(
        self,
        ctx: NovelContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> bool:
        """Plan the chapters, then promote the created ones to the RAG chapter type.

        Returns:
            bool: True when the chapters are planned and promoted; False on planning failure.
        """
        if not await super().plan_chapters_phase(ctx, send_to, **kwargs):
            return False
        for index, chapter in enumerate(ctx.child_contexts):
            ctx.child_contexts[index] = RagChapterContext.model_validate(vars(chapter))
        return True


class RAGChapterCompose[CTX: ChapterContext](
    ChapterCompose[CTX, RagStoryContext],
    RAGStyleFetch,
    ABC,
):
    """Chapter-level RAG composition: every story's references are fetched before its scenes are planned.

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

    async def plan_stories_phase(
        self,
        ctx: CTX,
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
        source = "\n\n".join(part for part in (ctx.skill_section(), ctx.description) if part)
        docs = await self._fetch_style_docs(source, ctx.rag, f"story '{ctx.title}'", **kwargs)
        ctx.add_retrieved_styles([doc.as_prompt() for doc in docs])
        logger.debug(f"Retrieved {len(docs)} style reference(s) for story '{ctx.title}'")
