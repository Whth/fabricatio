"""RAG-extended scene composition: retrieve writing style references and digest them into a guideline."""

from abc import ABC
from typing import List, Unpack, cast

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
    """Scene composition extended with writing style retrieval."""

    rag_query: str = ""
    """Custom query guideline for style retrieval; the scene description is used when empty."""

    rag_limit: int = 0
    """Reference documents retrieved per refined query; 0 uses the default configuration (15)."""

    async def prepare_scene_requirement(
        self,
        ctx: SceneContext,
        **kwargs: Unpack[LLMKwargs],
    ) -> str:
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
        queries = await self.arefined_query(self.rag_query or ctx.description, **kwargs)
        if not queries:
            return []
        config = WritingStyleFetchConfig(limit=self.rag_limit) if self.rag_limit else WritingStyleFetchConfig.default()
        try:
            return await self.afetch_document(queries, config)
        except OSError:
            logger.warn("Writing style fetch failed (table missing?), skipping RAG injection")
            return []
