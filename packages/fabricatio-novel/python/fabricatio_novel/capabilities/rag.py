"""RAG-extended scene composition: retrieve writing style references and digest them into a guideline."""

from abc import ABC
from typing import ClassVar, List, Unpack, cast

from fabricatio_core import TEMPLATE_MANAGER, logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.rust import detect_language
from fabricatio_core.utils import cfg

cfg(["lancedb"])

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG

from fabricatio_novel.capabilities.scene import SceneCompose
from fabricatio_novel.config import novel_config
from fabricatio_novel.models.context.scene import SceneContext
from fabricatio_novel.models.rag import WritingStyleDocument, WritingStyleFetchConfig


class RAGCompose(SceneCompose, LancedbRAG[WritingStyleDocument, LancedbAddRAGConfig, WritingStyleFetchConfig], ABC):
    """Scene composition extended with writing style retrieval.

    Retrieval settings (query guideline, limit) are caller-owned on the
    context channel (:class:`~fabricatio_novel.models.context.rag.RAGChannel`)
    and propagated down to the scene contexts.
    """

    fetch_head: ClassVar[int] = 6
    """Number of search heads (sub-queries) requested for each question."""

    async def prepare_scene_requirement(
            self,
            ctx: SceneContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> str:
        """Render the scene requirement and append a writing style guideline from retrieved references."""
        requirement = await super().prepare_scene_requirement(ctx, **kwargs)
        docs = await self._fetch_style_docs(ctx, **kwargs)
        if docs:
            digest = await self._digest_style_docs(docs, ctx, **kwargs)
            if digest:
                requirement += "\n\n## Writing Style Guideline\n" + digest
        return requirement

    async def _digest_style_docs(
            self,
            docs: List[WritingStyleDocument],
            ctx: SceneContext,
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
        return cast(
            "str | None",
            await self.ageneric_string(prompt, **kwargs),
        )

    async def _fetch_style_docs(
            self,
            ctx: SceneContext,
            **kwargs: Unpack[LLMKwargs],
    ) -> List[WritingStyleDocument]:
        question = "\n".join(part for part in (ctx.description, ctx.rag_query) if part)
        queries = await self.arefined_query(question, **kwargs, k=self.fetch_head)
        logger.debug(f"fetch for\n{queries} ")
        if not queries:
            return []

        config = WritingStyleFetchConfig(limit=ctx.rag_limit)
        docs = await self.afetch_document(queries, config)
        docs = [doc for doc in docs if doc.as_prompt().strip()]
        logger.debug(f"fet {len(docs)} docs")
        if docs:
            docs = await self.arank_documents(question, docs, **kwargs)
        return docs[:config.limit]
