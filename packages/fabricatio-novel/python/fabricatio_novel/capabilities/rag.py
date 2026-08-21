"""RAG-extended scene composition: retrieve raw writing style references for story-bound scenes."""

from abc import ABC
from typing import List, Unpack

from fabricatio_core import logger
from fabricatio_core.decorators import logging_exec_time
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK
from fabricatio_core.utils import cfg

cfg(["lancedb"])

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig


class RAGCompose(SceneCompose, LancedbRAG[WritingStyleDocument, LancedbAddRAGConfig, WritingStyleFetchConfig], ABC):
    """Scene composition extended with writing style retrieval.

    Retrieval settings live on the context tree as opt-in
    :class:`~fabricatio_novel.models.context.rag.RagRetrieval`; retrieval is skipped when a
    context carries none. Retrieved documents render to plain reference texts held on the
    story context, broadcast to its scenes, and injected raw into every scene's write prompt
    between the before-story prefix and the story's scenes so far, so they stay in the
    prompt's prefix-cacheable region.
    """

    @logging_exec_time
    async def prepare_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Retrieve raw writing style references for the story before its scenes are planned.

        The documents render to plain texts held on the story context so the
        scenes it materializes inherit them; no condensation is applied.
        """
        await super().prepare_story(ctx, send_to, **kwargs)
        if ctx.rag is None:
            return
        docs = await self._fetch_style_docs(ctx, **kwargs)
        if not docs:
            return
        ctx.set_style_docs([doc.as_prompt() for doc in docs])
        logger.debug(f"Retrieved {len(docs)} style reference(s) for story '{ctx.title}'")

    async def _fetch_style_docs(
        self,
        ctx: StoryContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[WritingStyleDocument]:
        """Fetch the story's top style references by vector similarity.

        The story description (plus the optional query guideline) is used
        directly as the query; no refine or rerank LLM calls are made.
        """
        rag = ctx.rag
        if rag is None:
            return []
        question = "\n".join(part for part in (ctx.description, rag.query) if part)
        if not question:
            return []
        config = WritingStyleFetchConfig(limit=rag.limit)
        docs = await self.afetch_document([question], config)
        docs = [doc for doc in docs if doc.as_prompt().strip()]
        docs = docs[: config.limit]
        logger.info(f"Retrieved {len(docs)} writing style reference(s) for story '{ctx.title}'")
        return docs
