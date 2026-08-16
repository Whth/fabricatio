"""RAG-extended scene composition: retrieve writing style references and digest them into a guideline."""

from abc import ABC
from typing import ClassVar, List, Unpack, cast

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.decorators import logging_exec_time
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import TASK, detect_language
from fabricatio_core.utils import cfg

cfg(["lancedb"])

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.context.story import StoryContext
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig


class RAGCompose(SceneCompose, LancedbRAG[WritingStyleDocument, LancedbAddRAGConfig, WritingStyleFetchConfig], ABC):
    """Scene composition extended with writing style retrieval.

    Retrieval settings (query guideline, limit) are caller-owned on the
    context channel (:class:`~fabricatio_novel.models.context.rag.RAGChannel`)
    and propagated down to the scene contexts.
    """

    fetch_head: ClassVar[int] = 6
    """Number of search heads (sub-queries) requested for each question."""

    @logging_exec_time
    async def prepare_story(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Retrieve writing style references for the story before its scenes are planned.

        The documents are held on the story context so scene planning can
        align with them; :meth:`prepare_scenes` condenses the same documents
        into the per-scene writing guideline.
        """
        await super().prepare_story(ctx, send_to, **kwargs)
        docs = await self._fetch_style_docs(ctx, **kwargs)
        if not docs:
            return
        ctx.set_style_docs(docs)
        logger.debug(f"Retrieved {len(docs)} style reference(s) for story '{ctx.title}'")

    @logging_exec_time
    async def prepare_scenes(
        self,
        ctx: StoryContext,
        send_to: str | None = TASK,
        **kwargs: Unpack[LLMKwargs],
    ) -> None:
        """Interpolate all scene chains, then digest the story's held style docs once.

        The base phase interpolates every scene's character chain
        concurrently. The style references retrieved by :meth:`prepare_story`
        are then digested a single time against the story context, and the
        shared guideline is stored on the story and every scene context for
        the serial write phase.
        """
        await super().prepare_scenes(ctx, send_to, **kwargs)
        scenes = ctx.scene_context
        if not scenes or not ctx.style_docs:
            return
        digest = await self._digest_style_docs(ctx.style_docs, ctx, **kwargs)
        if not digest:
            return
        ctx.set_style_digest(digest)
        for scene in scenes:
            scene.set_style_digest(digest)
        logger.debug(f"Style guideline stored for story '{ctx.title}' ({len(digest)} chars)")

    async def prepare_scene_requirement(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Render the scene requirement and append the story-prepared writing style guideline."""
        requirement = await super().prepare_scene_requirement(ctx, **kwargs)
        if ctx.style_digest:
            requirement += "\n\n## Writing Style Guideline\n" + ctx.style_digest
            logger.debug(f"Style guideline appended to scene '{ctx.title}' requirement ({len(ctx.style_digest)} chars)")
        return requirement

    @logging_exec_time
    async def _digest_style_docs(
        self,
        docs: List[WritingStyleDocument],
        ctx: StoryContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> str | None:
        """Condense the raw reference documents into a writing style guideline string."""
        prompt = TEMPLATE_MANAGER.render_template(
            novel_config.writing_style_digest_template,
            {
                "sources": "\n\n".join(doc.as_prompt() for doc in docs),
                "scene_title": ctx.title,
                "scene_description": ctx.description,
                "language": ctx.language or detect_language(ctx.description),
                "writing_style": ctx.writing_style,
            },
        )
        digest = cast(
            "str | None",
            await self.ageneric_string(prompt, **kwargs),
        )
        logger.debug(f"Digested {len(docs)} style reference(s) for story '{ctx.title}':\n{digest}")
        return digest

    async def _fetch_style_docs(
        self,
        ctx: StoryContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> List[WritingStyleDocument]:
        question = "\n".join(part for part in (ctx.description, ctx.rag_query) if part)
        logger.debug(f"Refining style query for story '{ctx.title}': {question}")
        queries = await self.arefined_query(question, **kwargs, k=self.fetch_head)
        if not queries:
            return []
        logger.debug(f"Refined {len(queries)} search head(s) for story '{ctx.title}'")

        config = WritingStyleFetchConfig(limit=ctx.rag_limit)
        docs = await self.afetch_document(queries, config)
        docs = [doc for doc in docs if doc.as_prompt().strip()]
        logger.debug(f"Fetched {len(docs)} non-blank writing style doc(s) for story '{ctx.title}'")
        if docs:
            docs = await self.arank_documents(question, docs, **kwargs)
            logger.debug(f"Reranked to {len(docs)} writing style doc(s) for story '{ctx.title}'")
        docs = docs[: config.limit]
        logger.info(f"Retrieved {len(docs)} writing style reference(s) for story '{ctx.title}'")
        return docs
