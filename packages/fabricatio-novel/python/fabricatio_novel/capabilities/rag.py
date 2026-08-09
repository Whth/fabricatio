"""RAG-extended scene composition: retrieve writing style references for scene prompts."""

from abc import ABC
from typing import List, Unpack

from fabricatio_core import logger
from fabricatio_core.models.kwargs_types import LLMKwargs
from fabricatio_core.utils import cfg

cfg(["lancedb"])

from fabricatio_lancedb.capabilities.lancedb import LancedbAddRAGConfig, LancedbRAG

from fabricatio_novel.capabilities.scene import SceneCompose
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
            requirement += "\n\n## Writing Style References\n" + "\n".join(doc.as_prompt() for doc in docs)
        return requirement

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
            logger.warning("Writing style fetch failed (table missing?), skipping RAG injection")
            return []
